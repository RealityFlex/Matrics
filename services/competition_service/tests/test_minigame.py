"""
Мини-игра «Забег до пары»: жизни за учёбу, античит, рейтинг группы, недельные призы.
"""
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from services.competition_service import minigame
from services.shared.models.character import Character
from services.shared.models.minigame import GameLives, GameRun, GameWeeklyPrize
from services.shared.models.social import GroupMember, StudentGroup
from services.shared.models.user import User
from services.shared.timeutil import utcnow

BASE = "/games/runner"


@pytest.fixture(autouse=True)
def mocked_side_effects(monkeypatch):
    monkeypatch.setenv("GAME_LIVES_MAX", "20")
    monkeypatch.setenv("GAME_LIVES_START", "20")
    monkeypatch.setenv("GAME_LIFE_REGEN_MINUTES", "120")
    with patch.object(minigame, "grant_reward", AsyncMock(return_value={"coins_added": 1})) as grant, \
         patch.object(minigame, "notify_bot", AsyncMock(return_value=True)) as notify:
        yield {"grant": grant, "notify": notify}


async def make_user(db, username, character_name=None):
    user = User(username=username, email=f"{username}@test.local", coins=0)
    db.add(user)
    await db.flush()
    if character_name:
        db.add(Character(user_id=user.id, name=character_name))
    await db.commit()
    return user


async def make_group(db, name, users):
    group = StudentGroup(name=name, max_chat_id=777)
    db.add(group)
    await db.flush()
    for user in users:
        db.add(GroupMember(group_id=group.id, user_id=user.id))
    await db.commit()
    return group


@pytest.fixture
def backdate(test_db_session):
    async def _backdate(run_id, seconds):
        run = (await test_db_session.execute(select(GameRun).where(GameRun.id == run_id))).scalar_one()
        run.started_at = utcnow() - timedelta(seconds=seconds)
        await test_db_session.commit()
    return _backdate


@pytest.fixture
def run_game(client, backdate):
    async def _run(user_id, distance=600, coins=40, seconds=60, duration_ms=None):
        start = (await client.post(f"{BASE}/start?user_id={user_id}")).json()
        await backdate(start["run_id"], seconds)
        response = await client.post(
            f"{BASE}/runs/{start['run_id']}/finish?user_id={user_id}",
            json={"distance": distance, "coins": coins, "duration_ms": duration_ms or seconds * 1000},
        )
        return start, response
    return _run


@pytest.mark.asyncio
async def test_rewarded_run_grants_coins_and_server_computes_score(client, test_db_session, run_game, mocked_side_effects):
    user = await make_user(test_db_session, "runner1", "Анна")
    start, response = await run_game(user.id, distance=600, coins=43)
    assert start["rewarded"] is True
    body = response.json()
    assert response.status_code == 200, body
    assert body["score"] == 600 + 43 * minigame.SCORE_PER_COIN
    assert body["coins_awarded"] == 5          # ceil(43 / 10)
    assert body["new_record"] is True
    grant = mocked_side_effects["grant"].await_args.args[0]
    assert grant["source"] == "minigame" and grant["coins"] == 5


@pytest.mark.asyncio
async def test_finish_only_once(client, test_db_session, run_game):
    user = await make_user(test_db_session, "runner2")
    start, _ = await run_game(user.id)
    again = await client.post(f"{BASE}/runs/{start['run_id']}/finish?user_id={user.id}",
                              json={"distance": 600, "coins": 40, "duration_ms": 60000})
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_implausible_results_rejected(client, test_db_session, run_game):
    user = await make_user(test_db_session, "cheater")
    # 10 000 м за 60 с — быстрее максимальной скорости
    _, fast = await run_game(user.id, distance=10_000, coins=10, seconds=60)
    assert fast.status_code == 400
    # Заявленная длительность больше реального времени с момента старта
    _, long = await run_game(user.id, distance=300, coins=10, seconds=10, duration_ms=120_000)
    assert long.status_code == 400
    # Монет больше, чем помещается на трассе
    _, coins = await run_game(user.id, distance=100, coins=500, seconds=30)
    assert coins.status_code == 400
    statuses = (await test_db_session.execute(select(GameRun.status).where(GameRun.user_id == user.id))).scalars().all()
    assert statuses == ["rejected", "rejected", "rejected"]


@pytest.mark.asyncio
async def test_start_requires_a_life(client, test_db_session, run_game, monkeypatch):
    monkeypatch.setenv("GAME_LIVES_MAX", "1")
    monkeypatch.setenv("GAME_LIVES_START", "1")
    user = await make_user(test_db_session, "limited")
    start, response = await run_game(user.id, distance=300, coins=20)
    assert start["rewarded"] is True and response.status_code == 200
    denied = await client.post(f"{BASE}/start?user_id={user.id}")
    assert denied.status_code == 403
    overview = (await client.get(f"{BASE}/overview?user_id={user.id}")).json()
    assert overview["lives"] == 0 and overview["lives_max"] == 1


@pytest.mark.asyncio
async def test_life_regenerates_over_time(client, test_db_session, monkeypatch):
    monkeypatch.setenv("GAME_LIVES_MAX", "3")
    monkeypatch.setenv("GAME_LIVES_START", "0")
    monkeypatch.setenv("GAME_LIFE_REGEN_MINUTES", "60")
    user = await make_user(test_db_session, "regen")
    test_db_session.add(GameLives(user_id=user.id, lives=0, last_regen_at=utcnow() - timedelta(hours=2, minutes=5)))
    await test_db_session.commit()
    overview = (await client.get(f"{BASE}/overview?user_id={user.id}")).json()
    assert overview["lives"] == 2
    assert overview["next_life_at"]


@pytest.mark.asyncio
async def test_abandon_refunds_life(client, test_db_session, monkeypatch):
    monkeypatch.setenv("GAME_LIVES_MAX", "1")
    monkeypatch.setenv("GAME_LIVES_START", "1")
    user = await make_user(test_db_session, "quitter")
    start = (await client.post(f"{BASE}/start?user_id={user.id}")).json()
    assert start["lives"] == 0
    abandoned = await client.post(f"{BASE}/runs/{start['run_id']}/abandon?user_id={user.id}")
    assert abandoned.status_code == 200, abandoned.text
    overview = (await client.get(f"{BASE}/overview?user_id={user.id}")).json()
    assert overview["lives"] == 1
    again = await client.post(f"{BASE}/runs/{start['run_id']}/abandon?user_id={user.id}")
    assert again.status_code == 409


@pytest.mark.asyncio
async def test_daily_coin_cap(client, test_db_session, run_game, monkeypatch):
    monkeypatch.setenv("GAME_DAILY_COIN_CAP", "7")
    user = await make_user(test_db_session, "capped")
    _, first = await run_game(user.id, distance=900, coins=100)
    _, second = await run_game(user.id, distance=900, coins=100)
    assert first.json()["coins_awarded"] == 7          # потолок за забег 10, но дневной — 7
    assert second.json()["coins_awarded"] == 0


@pytest.mark.asyncio
async def test_new_start_abandons_previous_run(client, test_db_session):
    user = await make_user(test_db_session, "restarter")
    first = (await client.post(f"{BASE}/start?user_id={user.id}")).json()
    await client.post(f"{BASE}/start?user_id={user.id}")
    late = await client.post(f"{BASE}/runs/{first['run_id']}/finish?user_id={user.id}",
                             json={"distance": 10, "coins": 0, "duration_ms": 1000})
    assert late.status_code == 409


@pytest.mark.asyncio
async def test_group_leaderboard_uses_best_run_of_week(client, test_db_session, run_game):
    anna = await make_user(test_db_session, "anna_r", "Анна")
    ivan = await make_user(test_db_session, "ivan_r", "Иван")
    outsider = await make_user(test_db_session, "outsider_r", "Чужой")
    await make_group(test_db_session, "ИВТ-11", [anna, ivan])
    await run_game(anna.id, distance=500, coins=10)
    await run_game(anna.id, distance=300, coins=0)
    await run_game(ivan.id, distance=700, coins=20)
    await run_game(outsider.id, distance=5000, coins=100, seconds=200)

    board = (await client.get(f"{BASE}/leaderboard?user_id={anna.id}")).json()
    assert board["scope"] == "group" and board["group_name"] == "ИВТ-11"
    assert [(e["name"], e["score"]) for e in board["entries"]] == [("Иван", 800), ("Анна", 550)]
    assert board["me"]["rank"] == 2

    overview = (await client.get(f"{BASE}/overview?user_id={anna.id}")).json()
    assert overview["week"] == {"start": overview["week"]["start"], "best": 550, "rank": 2}
    assert overview["best_score"] == 550 and overview["top"][1]["is_me"] is True

    everyone = (await client.get(f"{BASE}/leaderboard?scope=all&user_id={anna.id}")).json()
    assert everyone["entries"][0]["name"] == "Чужой"


@pytest.mark.asyncio
async def test_weekly_prizes_settled_once(client, test_db_session, mocked_side_effects):
    anna = await make_user(test_db_session, "anna_w", "Анна")
    ivan = await make_user(test_db_session, "ivan_w", "Иван")
    await make_group(test_db_session, "ИВТ-12", [anna, ivan])
    last_week = utcnow() - timedelta(days=7)
    test_db_session.add_all([
        GameRun(user_id=anna.id, seed=1, status="finished", score=900, started_at=last_week),
        GameRun(user_id=ivan.id, seed=2, status="finished", score=400, started_at=last_week),
    ])
    await test_db_session.commit()

    overview = (await client.get(f"{BASE}/overview?user_id={anna.id}")).json()
    assert overview["last_week_prize"]["place"] == 1 and overview["last_week_prize"]["coins"] == 15
    grants = [call.args[0] for call in mocked_side_effects["grant"].await_args_list]
    assert sorted(g["coins"] for g in grants) == [10, 15]
    notify = mocked_side_effects["notify"].await_args
    assert notify.args[0] == "/notifications/game-weekly-results" and notify.args[1]["chat_id"] == 777

    await client.get(f"{BASE}/overview?user_id={ivan.id}")
    assert mocked_side_effects["grant"].await_count == 2  # повторно не выдаётся
    prizes = (await test_db_session.execute(select(GameWeeklyPrize))).scalars().all()
    assert len(prizes) == 2 and all(p.granted_at for p in prizes)
