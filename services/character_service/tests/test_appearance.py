"""
Тесты кастомизации: каталог, разблокировка за посещаемость, покупка, экипировка, снимки.
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import insert, select

from services.character_service.appearance import seed_appearance_catalog, write_daily_snapshots
from services.shared.models.appearance import AppearanceSet
from services.shared.models.character import Character, CharacterSnapshot
from services.shared.models.lesson import Lesson, LessonAttendance, lesson_groups
from services.shared.models.social import GroupMember, StudentGroup
from services.shared.models.user import User

NOW = datetime.now(timezone.utc)


@pytest.fixture(autouse=True)
def _no_realtime():
    with patch("services.character_service.appearance.push_user_event", new=AsyncMock()), \
         patch("services.character_service.appearance.push_parameters_update", new=AsyncMock()):
        yield


@pytest_asyncio.fixture
async def world(test_db_session):
    await seed_appearance_catalog(test_db_session)
    user = User(username="hero", email="hero@example.com", coins=160)
    test_db_session.add(user)
    await test_db_session.flush()
    test_db_session.add(Character(user_id=user.id, name="Герой"))
    await test_db_session.commit()
    sets = {s.code: s.id for s in (await test_db_session.execute(select(AppearanceSet))).scalars()}
    return {"user": user.id, "sets": sets}


async def attend_lessons(session, user_id, count):
    group = StudentGroup(name="Группа", creator_id=user_id)
    session.add(group)
    await session.flush()
    session.add(GroupMember(group_id=group.id, user_id=user_id, joined_at=NOW - timedelta(days=60)))
    for i in range(count):
        lesson = Lesson(name=f"Пара {i}", start_time=NOW - timedelta(days=count - i, hours=2),
                        end_time=NOW - timedelta(days=count - i, hours=1), created_by=user_id)
        session.add(lesson)
        await session.flush()
        await session.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=group.id))
        session.add(LessonAttendance(lesson_id=lesson.id, user_id=user_id))
    await session.commit()


class TestAppearance:
    @pytest.mark.asyncio
    async def test_catalog_has_default_sets(self, client, world):
        response = await client.get("/characters/appearance/catalog", params={"user_id": world["user"]})
        assert response.status_code == 200
        data = response.json()
        assert len(data["characters"]) == 5 and len(data["environments"]) == 5
        basic = next(i for i in data["characters"] if i["code"] == "student_basic")
        scholar = next(i for i in data["characters"] if i["code"] == "scholar")
        assert basic["unlocked"] is True
        assert scholar["unlocked"] is False and scholar["progress"] == {"current": 0, "required": 5}

    @pytest.mark.asyncio
    async def test_locked_set_cannot_be_equipped(self, client, world):
        response = await client.post(
            f"/characters/user/{world['user']}/appearance/equip",
            params={"user_id": world["user"]}, json={"set_id": world["sets"]["scholar"]},
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_attendance_unlocks_and_equip(self, client, world, test_db_session):
        await attend_lessons(test_db_session, world["user"], 5)
        response = await client.post(f"/characters/user/{world['user']}/appearance/check-unlocks")
        codes = {item["code"] for item in response.json()["unlocked"]}
        assert "scholar" in codes

        response = await client.post(
            f"/characters/user/{world['user']}/appearance/equip",
            params={"user_id": world["user"]}, json={"set_id": world["sets"]["scholar"]},
        )
        assert response.status_code == 200
        assert response.json()["active_character_set"]["code"] == "scholar"

        character = await client.get(f"/characters/user/{world['user']}")
        assert character.json()["active_character_set"]["code"] == "scholar"
        assert character.json()["mood"] == "neutral"

    @pytest.mark.asyncio
    async def test_purchase_with_coins(self, client, world):
        url = f"/characters/user/{world['user']}/appearance/purchase"
        first = await client.post(url, params={"user_id": world["user"]}, json={"set_id": world["sets"]["night_owl"]})
        assert first.status_code == 200, first.text
        assert first.json()["coins"] == 10
        again = await client.post(url, params={"user_id": world["user"]}, json={"set_id": world["sets"]["night_owl"]})
        assert again.status_code == 400
        poor = await client.post(url, params={"user_id": world["user"]}, json={"set_id": world["sets"]["campus_park"]})
        assert poor.status_code == 400
        not_for_sale = await client.post(url, params={"user_id": world["user"]}, json={"set_id": world["sets"]["scholar"]})
        assert not_for_sale.status_code == 400

    @pytest.mark.asyncio
    async def test_daily_snapshot_upsert(self, world, test_db_session):
        assert await write_daily_snapshots(test_db_session) == 1
        assert await write_daily_snapshots(test_db_session) == 1
        rows = (await test_db_session.execute(select(CharacterSnapshot))).scalars().all()
        assert len(rows) == 1 and rows[0].coins == 160
