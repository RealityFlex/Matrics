"""
Тесты основного сценария: отметка на занятии → награда → серия, а также
«заморозка» пропусков и тестовый импорт расписания.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy import insert, select

from services.event_service import lesson_checkin, streak_service
from services.shared import attendance_codes as codes
from services.shared.models.lesson import Lesson, LessonAttendance, LessonMiss, LessonMissStatus, lesson_groups
from services.shared.models.social import GroupMember, StudentGroup
from services.shared.models.user import User
from services.test_utils import MockServiceClient

NOW = datetime.now(timezone.utc)
SECRET = "test-secret"


def reward_response(user_id=1):
    return {
        "user_id": user_id,
        "coins_added": 5,
        "intelligence_added": 10,
        "satisfaction_added": 5,
        "level_up": False,
        "achievements_earned": [],
        "character": {"satisfaction_before": 50, "satisfaction": 55, "mood": "neutral"},
        "unlocked_sets": [],
    }


@pytest.fixture(autouse=True)
def _reset_state():
    lesson_checkin._failed_attempts.clear()
    yield
    lesson_checkin._failed_attempts.clear()


@pytest.fixture
def reward_mock():
    mock = MockServiceClient("reward")
    mock.set_response("/rewards/grant", reward_response())
    mock.set_response("/notifications/", {"success": True})
    with patch("services.event_service.lesson_checkin.ServiceClient", return_value=mock), \
         patch("services.event_service.lesson_checkin.push_user_event", new=AsyncMock()):
        yield mock


@pytest_asyncio.fixture
async def setup(test_db_session):
    """Группа, студент в группе, посторонний пользователь и идущее сейчас занятие"""
    student = User(username="student1", email="s1@example.com")
    stranger = User(username="stranger", email="s2@example.com")
    test_db_session.add_all([student, stranger])
    await test_db_session.flush()
    group = StudentGroup(name="КРСО-15-22", creator_id=student.id)
    test_db_session.add(group)
    await test_db_session.flush()
    test_db_session.add(GroupMember(group_id=group.id, user_id=student.id, joined_at=NOW - timedelta(days=30)))
    lesson = Lesson(
        name="Математическое моделирование",
        start_time=NOW - timedelta(minutes=10),
        end_time=NOW + timedelta(minutes=80),
        reward_coins=5,
        reward_intelligence_points=10,
        reward_satisfaction=5,
        created_by=student.id,
        qr_secret=SECRET,
    )
    test_db_session.add(lesson)
    await test_db_session.flush()
    await test_db_session.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=group.id))
    await test_db_session.commit()
    return {"student": student.id, "stranger": stranger.id, "group": group.id, "lesson": lesson.id}


def current_code(lesson_id):
    return codes.current_lesson_code(SECRET, lesson_id)


class TestCheckIn:
    @pytest.mark.asyncio
    async def test_valid_code_grants_reward_with_satisfaction(self, client: AsyncClient, setup, reward_mock):
        response = await client.post(
            f"/lessons/{setup['lesson']}/check-in",
            params={"user_id": setup["student"]},
            json={"code": current_code(setup["lesson"]), "method": "code"},
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["status"] == "checked_in"
        assert data["rewards_status"] == "granted"
        assert data["rewards"] == {"coins": 5, "intelligence_points": 10, "satisfaction": 5}
        assert data["character"]["satisfaction"] == 55
        assert data["streak"]["current"] == 1

    @pytest.mark.asyncio
    async def test_legacy_endpoint_requires_code(self, client: AsyncClient, setup, reward_mock):
        response = await client.post(
            f"/lessons/{setup['lesson']}/attendance", params={"user_id": setup["student"]}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_legacy_endpoint_with_code(self, client: AsyncClient, setup, reward_mock):
        response = await client.post(
            f"/lessons/{setup['lesson']}/attendance",
            params={"user_id": setup["student"]},
            json={"code": current_code(setup["lesson"])},
        )
        assert response.status_code == 201, response.text
        assert response.json()["verification_method"] == "message"

    @pytest.mark.asyncio
    async def test_wrong_code_rejected(self, client: AsyncClient, setup, reward_mock):
        good = current_code(setup["lesson"])
        wrong = f"{(int(good) + 1) % 10000:04d}"
        response = await client.post(
            f"/lessons/{setup['lesson']}/check-in",
            params={"user_id": setup["student"]},
            json={"code": wrong},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_stale_code_rejected(self, client: AsyncClient, setup, reward_mock):
        old = codes.lesson_code(SECRET, setup["lesson"], codes.current_window() - 5)
        if old == current_code(setup["lesson"]):
            pytest.skip("случайное совпадение кодов")
        response = await client.post(
            f"/lessons/{setup['lesson']}/check-in",
            params={"user_id": setup["student"]},
            json={"code": old},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_not_group_member_rejected(self, client: AsyncClient, setup, reward_mock):
        response = await client.post(
            f"/lessons/{setup['lesson']}/check-in",
            params={"user_id": setup["stranger"]},
            json={"code": current_code(setup["lesson"])},
        )
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_double_check_in_rewards_once(self, client: AsyncClient, setup, reward_mock, test_db_session):
        calls = []
        original = reward_mock.post

        async def tracking_post(url, json=None, **kwargs):
            if "/rewards/grant" in url:
                calls.append(json)
            return await original(url, json, **kwargs)

        reward_mock.post = tracking_post
        for _ in range(2):
            response = await client.post(
                f"/lessons/{setup['lesson']}/check-in",
                params={"user_id": setup["student"]},
                json={"code": current_code(setup["lesson"])},
            )
            assert response.status_code == 200
        assert response.json()["status"] == "already"
        assert len(calls) == 1
        assert calls[0]["satisfaction"] == 5 and calls[0]["source"] == "lesson_attendance"
        rows = (await test_db_session.execute(select(LessonAttendance))).scalars().all()
        assert len(rows) == 1

    @pytest.mark.asyncio
    async def test_reward_failure_is_reported_as_pending(self, client: AsyncClient, setup):
        failing = MockServiceClient("reward")
        failing.post_mock.side_effect = Exception("reward-service down")
        with patch("services.event_service.lesson_checkin.ServiceClient", return_value=failing), \
             patch("services.event_service.lesson_checkin.push_user_event", new=AsyncMock()):
            response = await client.post(
                f"/lessons/{setup['lesson']}/check-in",
                params={"user_id": setup["student"]},
                json={"code": current_code(setup["lesson"])},
            )
        assert response.status_code == 200
        assert response.json()["rewards_status"] == "pending"

    @pytest.mark.asyncio
    async def test_bruteforce_limited(self, client: AsyncClient, setup, reward_mock):
        good = current_code(setup["lesson"])
        wrong = f"{(int(good) + 5000) % 10000:04d}"
        statuses = []
        for _ in range(6):
            response = await client.post(
                f"/lessons/{setup['lesson']}/check-in",
                params={"user_id": setup["student"]},
                json={"code": wrong},
            )
            statuses.append(response.status_code)
        assert statuses[:5] == [400] * 5
        assert statuses[5] == 429

    @pytest.mark.asyncio
    async def test_window_enforced(self, client: AsyncClient, setup, reward_mock, test_db_session, monkeypatch):
        monkeypatch.setenv("CHECKIN_ENFORCE_WINDOW", "true")
        lesson = (await test_db_session.execute(select(Lesson).where(Lesson.id == setup["lesson"]))).scalar_one()
        lesson.start_time = NOW + timedelta(hours=3)
        lesson.end_time = NOW + timedelta(hours=4)
        await test_db_session.commit()
        response = await client.post(
            f"/lessons/{setup['lesson']}/check-in",
            params={"user_id": setup["student"]},
            json={"code": current_code(setup["lesson"])},
        )
        assert response.status_code == 400


class TestTeacherEndpoints:
    @pytest.mark.asyncio
    async def test_qr_contains_deep_link(self, client: AsyncClient, setup, monkeypatch):
        monkeypatch.setenv("MAX_BOT_USERNAME", "matrix_bot")
        response = await client.get(f"/lessons/{setup['lesson']}/qr")
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == current_code(setup["lesson"])
        assert data["deep_link"] == f"https://max.ru/matrix_bot?startapp=att-{setup['lesson']}-{data['code']}"

    @pytest.mark.asyncio
    async def test_qr_requires_admin_token_when_configured(self, client: AsyncClient, setup, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "secret-admin")
        response = await client.get(f"/lessons/{setup['lesson']}/qr")
        assert response.status_code == 401
        response = await client.get(f"/lessons/{setup['lesson']}/qr", headers={"X-Admin-Token": "secret-admin"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_lesson_listing_hides_code(self, client: AsyncClient, setup):
        response = await client.get("/lessons/", params={"user_id": setup["student"]})
        assert response.status_code == 200
        assert all(item["qr_token"] is None for item in response.json())

    @pytest.mark.asyncio
    async def test_manual_attendance(self, client: AsyncClient, setup, reward_mock):
        response = await client.post(
            f"/lessons/{setup['lesson']}/attendance/manual", json={"user_id": setup["student"]}
        )
        assert response.status_code == 200
        assert response.json()["verification_method"] == "manual"

    @pytest.mark.asyncio
    async def test_schedule_shows_current_lesson(self, client: AsyncClient, setup):
        response = await client.get(f"/schedule/users/{setup['student']}")
        assert response.status_code == 200
        data = response.json()
        assert data["current"]["id"] == setup["lesson"]
        assert data["current"]["attended"] is False


class TestStreakFreeze:
    @pytest_asyncio.fixture
    async def ended_lesson(self, test_db_session, setup):
        lesson = Lesson(
            name="Основы программирования",
            start_time=NOW - timedelta(minutes=120),
            end_time=NOW - timedelta(minutes=30),
            reward_coins=5,
            reward_intelligence_points=10,
            created_by=setup["student"],
            qr_secret=SECRET,
        )
        test_db_session.add(lesson)
        await test_db_session.flush()
        await test_db_session.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=setup["group"]))
        await test_db_session.commit()
        return lesson.id

    @pytest.fixture
    def bot_mock(self):
        mock = MockServiceClient("max_bot")
        mock.set_response("/", {"success": True})
        with patch("services.event_service.streak_service.ServiceClient", return_value=mock):
            yield mock

    @pytest.mark.asyncio
    async def test_miss_detected_and_frozen(self, client, test_db_session, setup, ended_lesson, bot_mock):
        result = await streak_service.process_lesson_misses(
            test_db_session, now=NOW, tracking_start=NOW - timedelta(days=1)
        )
        assert result["created"] == 1
        miss = (await test_db_session.execute(select(LessonMiss))).scalar_one()
        assert miss.status == LessonMissStatus.PENDING

        response = await client.post(
            f"/streaks/users/{setup['student']}/freeze",
            params={"user_id": setup["student"]},
            json={"miss_id": miss.id},
        )
        assert response.status_code == 200, response.text
        assert response.json()["status"] == LessonMissStatus.FROZEN

        again = await client.post(
            f"/streaks/users/{setup['student']}/freeze",
            params={"user_id": setup["student"]},
            json={"miss_id": miss.id},
        )
        assert again.status_code == 409

    @pytest.mark.asyncio
    async def test_history_before_tracking_start_ignored(self, test_db_session, setup, ended_lesson, bot_mock):
        result = await streak_service.process_lesson_misses(test_db_session, now=NOW, tracking_start=NOW)
        assert result["created"] == 0

    @pytest.mark.asyncio
    async def test_expired_miss_penalized(self, test_db_session, setup, ended_lesson, bot_mock, monkeypatch):
        monkeypatch.setenv("STREAK_FREEZE_DECISION_MIN", "1")
        await streak_service.process_lesson_misses(test_db_session, now=NOW, tracking_start=NOW - timedelta(days=1))
        result = await streak_service.process_lesson_misses(
            test_db_session, now=NOW + timedelta(minutes=5), tracking_start=NOW - timedelta(days=1)
        )
        assert result["penalized"] == 1
        miss = (await test_db_session.execute(select(LessonMiss))).scalar_one()
        assert miss.status == LessonMissStatus.PENALIZED

    @pytest.mark.asyncio
    async def test_freeze_limit(self, client, test_db_session, setup, bot_mock, monkeypatch):
        monkeypatch.setenv("STREAK_FREEZES_PER_30D", "1")
        misses = []
        for offset in (200, 100):
            lesson = Lesson(
                name=f"Пара {offset}", start_time=NOW - timedelta(minutes=offset + 90),
                end_time=NOW - timedelta(minutes=offset), created_by=setup["student"], qr_secret=SECRET,
            )
            test_db_session.add(lesson)
            await test_db_session.flush()
            miss = LessonMiss(lesson_id=lesson.id, user_id=setup["student"], status=LessonMissStatus.PENDING,
                              decision_deadline=NOW + timedelta(hours=1))
            test_db_session.add(miss)
            await test_db_session.flush()
            misses.append(miss.id)
        await test_db_session.commit()

        first = await client.post(f"/streaks/users/{setup['student']}/freeze",
                                  params={"user_id": setup["student"]}, json={"miss_id": misses[0]})
        second = await client.post(f"/streaks/users/{setup['student']}/freeze",
                                   params={"user_id": setup["student"]}, json={"miss_id": misses[1]})
        assert first.status_code == 200
        assert second.status_code == 409


class TestScheduleImport:
    @pytest.mark.asyncio
    async def test_csv_import_marks_simulated(self, client: AsyncClient, setup, test_db_session):
        csv_text = (
            "name,start_time,duration_minutes,location,group\n"
            "Физика,2026-10-01T09:00:00,90,А-101,КРСО-15-22\n"
            "Химия,2026-10-01T10:40:00,90,Б-12,Несуществующая\n"
        )
        response = await client.post("/lessons/import", json={"created_by": setup["student"], "csv_text": csv_text})
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["created"] == 1
        assert len(data["errors"]) == 1
        lesson = (await test_db_session.execute(
            select(Lesson).where(Lesson.id == data["lesson_ids"][0])
        )).scalar_one()
        assert lesson.source == "test_import" and lesson.is_simulated is True
        # 09:00 по Москве = 06:00 UTC
        start = lesson.start_time if lesson.start_time.tzinfo else lesson.start_time.replace(tzinfo=timezone.utc)
        assert start.hour == 6

        deleted = await client.delete(f"/lessons/import/{data['batch_id']}")
        assert deleted.json()["deleted"] == 1
