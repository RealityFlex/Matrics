"""
Тесты дашборда куратора: посещаемость группы, риск-лист, недельная динамика, доступ.
"""
import time
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from sqlalchemy import insert

from services.shared.max_auth import sign_init_data
from services.shared.models.character import Character, CharacterSnapshot
from services.shared.models.lesson import Lesson, LessonAttendance, lesson_groups
from services.shared.models.social import GroupMember, StudentGroup, group_curators
from services.shared.models.user import User

NOW = datetime.now(timezone.utc)


@pytest_asyncio.fixture
async def group_data(test_db_session):
    users = [User(username=f"st{i}", email=f"st{i}@example.com") for i in range(3)]
    curator = User(username="curator", email="max_4242@max.local", role="curator")
    outsider_curator = User(username="other", email="max_5151@max.local", role="curator")
    test_db_session.add_all(users + [curator, outsider_curator])
    await test_db_session.flush()
    group = StudentGroup(name="ИВТ-21")
    test_db_session.add(group)
    await test_db_session.flush()
    for user, sat in zip(users, (80, 20, 60)):
        test_db_session.add(GroupMember(group_id=group.id, user_id=user.id, joined_at=NOW - timedelta(days=60)))
        test_db_session.add(Character(user_id=user.id, name=user.username, satisfaction=sat))
        test_db_session.add(CharacterSnapshot(user_id=user.id, snapshot_date=(NOW - timedelta(days=8)).date(),
                                              satisfaction=80, intelligence_level=1, intelligence_points=0))
    lessons = []
    for i in range(2):
        lesson = Lesson(name=f"Пара {i}", start_time=NOW - timedelta(days=2 - i, hours=2),
                        end_time=NOW - timedelta(days=2 - i, hours=1), created_by=curator.id)
        test_db_session.add(lesson)
        await test_db_session.flush()
        await test_db_session.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=group.id))
        lessons.append(lesson)
    # st0 — оба занятия, st1 — ни одного, st2 — одно
    test_db_session.add_all([
        LessonAttendance(lesson_id=lessons[0].id, user_id=users[0].id),
        LessonAttendance(lesson_id=lessons[1].id, user_id=users[0].id),
        LessonAttendance(lesson_id=lessons[1].id, user_id=users[2].id),
    ])
    await test_db_session.execute(insert(group_curators).values(group_id=group.id, user_id=curator.id))
    await test_db_session.commit()
    return {"group": group.id, "users": [u.id for u in users]}


def curator_headers(max_id):
    data = sign_init_data({"auth_date": int(time.time()), "user": {"id": max_id}}, "test-bot-token")
    return {"X-Max-Init-Data": data}


class TestCuratorDashboard:
    @pytest.mark.asyncio
    async def test_attendance_rate(self, client, group_data):
        response = await client.get(f"/stats/curator/groups/{group_data['group']}/attendance")
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["lessons_total"] == 2 and data["members_total"] == 3
        assert data["attendance_rate"] == round(3 / 6, 3)
        by_user = {s["user_id"]: s for s in data["per_student"]}
        assert by_user[group_data["users"][0]]["rate"] == 1.0
        assert by_user[group_data["users"][1]]["rate"] == 0.0

    @pytest.mark.asyncio
    async def test_at_risk_list(self, client, group_data):
        response = await client.get(f"/stats/curator/groups/{group_data['group']}/at-risk")
        assert response.status_code == 200
        students = response.json()["students"]
        assert students[0]["user_id"] == group_data["users"][1]
        assert "satisfaction_drop" in students[0]["flags"] and "low_satisfaction" in students[0]["flags"]
        assert group_data["users"][0] not in [s["user_id"] for s in students]

    @pytest.mark.asyncio
    async def test_weekly(self, client, group_data):
        response = await client.get(f"/stats/curator/groups/{group_data['group']}/weekly", params={"weeks": 4})
        assert response.status_code == 200
        assert len(response.json()["weeks"]) == 4

    @pytest.mark.asyncio
    async def test_curator_scope(self, client, group_data, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "adm")
        url = f"/stats/curator/groups/{group_data['group']}/attendance"
        assert (await client.get(url)).status_code == 401
        assert (await client.get(url, headers=curator_headers(4242))).status_code == 200
        assert (await client.get(url, headers=curator_headers(5151))).status_code == 403
        assert (await client.get(url, headers={"X-Admin-Token": "adm"})).status_code == 200
        groups = await client.get("/stats/curator/groups", headers=curator_headers(4242))
        assert [g["id"] for g in groups.json()["groups"]] == [group_data["group"]]


class TestCuratorCabinet:
    @pytest.mark.asyncio
    async def test_lessons_nudge_support(self, client, group_data, test_db_session, monkeypatch):
        from unittest.mock import AsyncMock
        from services.shared.models.lesson import SupportRequest
        from services.statistics_service import curator

        notify = AsyncMock(return_value=True)
        monkeypatch.setattr(curator, "notify_bot", notify)
        gid, students = group_data["group"], group_data["users"]

        lessons = await client.get(f"/stats/curator/groups/{gid}/lessons")
        assert lessons.status_code == 200 and isinstance(lessons.json(), list)

        nudge = await client.post(f"/stats/curator/students/{students[1]}/nudge", headers=curator_headers(4242))
        assert nudge.status_code == 200
        assert notify.call_args.args[0] == "/notifications/curator-nudge"
        foreign = await client.post(f"/stats/curator/students/{students[1]}/nudge", headers=curator_headers(5151))
        assert foreign.status_code == 403

        test_db_session.add(SupportRequest(user_id=students[2], source="student", message="Тяжело", status="open"))
        await test_db_session.commit()
        support = (await client.get(f"/stats/curator/groups/{gid}/support")).json()
        assert support[0]["message"] == "Тяжело"
        risk = (await client.get(f"/stats/curator/groups/{gid}/at-risk")).json()["students"]
        assert risk[0]["user_id"] == students[2] and "asked_help" in risk[0]["flags"]
        resolved = await client.post(f"/stats/curator/support/{support[0]['id']}/resolve")
        assert resolved.status_code == 200
        assert (await client.get(f"/stats/curator/groups/{gid}/support")).json() == []

    @pytest.mark.asyncio
    async def test_digest(self, client, group_data, monkeypatch):
        from unittest.mock import AsyncMock
        from services.statistics_service import curator

        notify = AsyncMock(return_value=True)
        monkeypatch.setattr(curator, "notify_bot", notify)
        result = (await client.post("/stats/curator/digest/send")).json()
        assert result == {"curators": 1, "delivered": 1}
        payload = notify.call_args.args[1]
        assert payload["groups"][0]["group_name"] == "ИВТ-21" and payload["groups"][0]["at_risk"]
