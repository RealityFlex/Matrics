"""
Тесты вовлечённости: командная цель пары, итоги в чат, напоминания, «Нужна помощь».
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import insert, select

from services.event_service import engagement
from services.shared.models.character import Character
from services.shared.models.lesson import Lesson, LessonAttendance, LessonGroupGoal, LessonMiss, LessonMissStatus, SupportRequest, lesson_groups
from services.shared.models.social import GroupMember, StudentGroup, group_curators
from services.shared.models.user import User

NOW = datetime.now(timezone.utc)


@pytest.fixture
def calls():
    recorded = {"bot": [], "reward": []}

    async def fake_notify(endpoint, payload):
        recorded["bot"].append((endpoint, payload))
        return True

    async def fake_reward(payload):
        recorded["reward"].append(payload)
        return {"ok": True}

    with patch.object(engagement, "notify_bot", new=fake_notify), patch.object(engagement, "grant_reward", new=fake_reward):
        yield recorded


@pytest_asyncio.fixture
async def group(test_db_session):
    users = [User(username=f"u{i}", email=f"u{i}@example.com") for i in range(5)]
    curator = User(username="cur", email="cur@example.com", role="curator")
    test_db_session.add_all(users + [curator])
    await test_db_session.flush()
    grp = StudentGroup(name="ПИ-21", creator_id=curator.id, max_chat_id=-100500, team_goal_percent=80)
    test_db_session.add(grp)
    await test_db_session.flush()
    for u in users:
        test_db_session.add(GroupMember(group_id=grp.id, user_id=u.id, joined_at=NOW - timedelta(days=10)))
        test_db_session.add(Character(user_id=u.id, name=u.username, satisfaction=50))
    await test_db_session.execute(insert(group_curators).values(group_id=grp.id, user_id=curator.id))
    lesson = Lesson(name="Физика", start_time=NOW - timedelta(minutes=10), end_time=NOW + timedelta(minutes=80),
                    created_by=curator.id, location="А-1")
    test_db_session.add(lesson)
    await test_db_session.flush()
    await test_db_session.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=grp.id))
    await test_db_session.commit()
    return {"users": [u.id for u in users], "curator": curator.id, "group": grp.id, "lesson": lesson.id}


async def attend(session, lesson_id, user_ids):
    for uid in user_ids:
        session.add(LessonAttendance(lesson_id=lesson_id, user_id=uid))
    await session.commit()


class TestGroupGoal:
    @pytest.mark.asyncio
    async def test_goal_reached_rewards_everyone_and_posts_to_chat(self, test_db_session, group, calls):
        users = group["users"]
        await attend(test_db_session, group["lesson"], users[:3])
        bonuses = await engagement.process_group_goals(test_db_session, group["lesson"], users[2])
        assert bonuses == []  # 3 из 5 = 60% < 80%

        await attend(test_db_session, group["lesson"], [users[3]])
        bonuses = await engagement.process_group_goals(test_db_session, group["lesson"], users[3])
        assert sorted(b["user_id"] for b in bonuses) == sorted(users[:4])  # 80% — бонус всем отметившимся
        assert all(r["source"] == "group_goal" for r in calls["reward"])
        assert calls["bot"][0][0] == "/notifications/group-goal"
        assert calls["bot"][0][1]["chat_id"] == -100500 and calls["bot"][0][1]["percent"] == 80

        await attend(test_db_session, group["lesson"], [users[4]])
        late = await engagement.process_group_goals(test_db_session, group["lesson"], users[4])
        assert late == [{"user_id": users[4], "group_id": group["group"]}]  # опоздавший тоже получает бонус
        assert len([b for b in calls["bot"] if b[0] == "/notifications/group-goal"]) == 1  # в чат — один раз

    @pytest.mark.asyncio
    async def test_progress_needed(self, test_db_session, group):
        await attend(test_db_session, group["lesson"], group["users"][:2])
        lesson = (await test_db_session.execute(select(Lesson).where(Lesson.id == group["lesson"]))).scalar_one()
        item = engagement.public_progress(await engagement.group_progress(test_db_session, lesson))[0]
        assert item["attended"] == 2 and item["expected"] == 5 and item["needed"] == 2 and item["achieved"] is False


class TestReminderAndSummary:
    @pytest.mark.asyncio
    async def test_reminder_sent_once(self, test_db_session, group, calls):
        soon = Lesson(name="Химия", start_time=NOW + timedelta(minutes=8), end_time=NOW + timedelta(minutes=98),
                      created_by=group["curator"])
        test_db_session.add(soon)
        await test_db_session.flush()
        await test_db_session.execute(insert(lesson_groups).values(lesson_id=soon.id, group_id=group["group"]))
        await test_db_session.commit()
        assert await engagement.send_lesson_reminders(test_db_session, NOW) == 1
        assert await engagement.send_lesson_reminders(test_db_session, NOW) == 0
        direct = [p for e, p in calls["bot"] if e == "/notifications/lesson-reminder"]
        chat = [p for e, p in calls["bot"] if e == "/notifications/group-lesson-reminder"]
        assert len(direct) == 5 and len(chat) == 1

    @pytest.mark.asyncio
    async def test_summary_after_lesson(self, test_db_session, group, calls):
        lesson = (await test_db_session.execute(select(Lesson).where(Lesson.id == group["lesson"]))).scalar_one()
        lesson.start_time, lesson.end_time = NOW - timedelta(hours=2), NOW - timedelta(minutes=5)
        await test_db_session.commit()
        await attend(test_db_session, group["lesson"], group["users"][:4])
        sent = await engagement.send_lesson_summaries(test_db_session, NOW, NOW - timedelta(days=1))
        assert sent == 1
        assert await engagement.send_lesson_summaries(test_db_session, NOW, NOW - timedelta(days=1)) == 0
        summary = [p for e, p in calls["bot"] if e == "/notifications/group-lesson-summary"][0]
        assert summary["percent"] == 80 and summary["top_streaks"]


class TestSupport:
    @pytest.mark.asyncio
    async def test_student_request_goes_to_curator(self, client, test_db_session, group, calls):
        uid = group["users"][0]
        first = await client.post(f"/support/request?user_id={uid}", json={"message": "Не успеваю"})
        assert first.status_code == 200 and first.json()["status"] == "sent" and first.json()["curators_notified"] == 1
        again = await client.post(f"/support/request?user_id={uid}", json={})
        assert again.json()["status"] == "already_sent"
        note = [p for e, p in calls["bot"] if e == "/notifications/support-request"]
        assert len(note) == 1 and note[0]["curator_user_ids"] == [group["curator"]]

    @pytest.mark.asyncio
    async def test_help_offer_after_two_penalties(self, test_db_session, group, calls):
        uid = group["users"][1]
        for minutes in (300, 200):
            lesson = Lesson(name=f"L{minutes}", start_time=NOW - timedelta(minutes=minutes + 90),
                            end_time=NOW - timedelta(minutes=minutes), created_by=group["curator"])
            test_db_session.add(lesson)
            await test_db_session.flush()
            test_db_session.add(LessonMiss(lesson_id=lesson.id, user_id=uid, status=LessonMissStatus.PENALIZED))
        await test_db_session.commit()
        assert await engagement.offer_help_if_needed(test_db_session, [uid, group["users"][2]], NOW) == 1
        assert await engagement.offer_help_if_needed(test_db_session, [uid], NOW) == 0  # не чаще раза в неделю
        assert [p for e, p in calls["bot"] if e == "/notifications/help-offer"] == [{"user_id": uid}]
