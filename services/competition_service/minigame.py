"""
Мини-игра «Забег до пары» — раннер на главном экране мини-приложения.

Забег стоит жизнь. Жизни выдаются за учёбу (задача, привычка, пара, достижение)
и восстанавливаются по таймеру — игра не бесконечная. Монеты из забега ограничены
дневным потолком. Недельный рейтинг группы и призы топ-3 сохраняются.

Античит (MVP): очки считает сервер (дистанция + монеты × SCORE_PER_COIN); дистанция не
может превышать максимальную скорость × длительность, длительность — реальное время
с момента старта, монеты — плотность размещения на трассе; у забега один финиш.
"""
from __future__ import annotations

import logging
import math
import os
import secrets
from datetime import date, datetime, time, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import require_verified_user, resolve_acting_user_id
from services.shared.bot_notify import grant_reward, notify_bot
from services.shared.database import get_db
from services.shared.game_lives import consume_life, load_lives, refund_life, snapshot as lives_snapshot
from services.shared.models.character import Character
from services.shared.models.minigame import GameRun, GameWeeklyPrize
from services.shared.models.social import GroupMember, StudentGroup
from services.shared.models.user import User
from services.shared.timeutil import app_timezone, as_utc, utcnow

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/games/runner", tags=["mini-game"])

GAME = "runner"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def settings() -> Dict[str, object]:
    prizes = [int(x) for x in os.getenv("GAME_WEEKLY_PRIZES", "15,10,5").split(",") if x.strip().isdigit()]
    return {
        "daily_coin_cap": _int_env("GAME_DAILY_COIN_CAP", 30),
        "max_coins_per_run": _int_env("GAME_MAX_COINS_PER_RUN", 10),
        "pickups_per_coin": max(1, _int_env("GAME_PICKUPS_PER_COIN", 10)),
        "weekly_prizes": prizes,
    }


# Параметры, общие с клиентом (frontend/src/features/game/runnerEngine.js)
SCORE_PER_COIN = 5
MAX_SPEED = 32.0            # клиент ограничен 30 м/с — запас на погрешность таймеров
MIN_COIN_SPACING = 2.0      # монеты на трассе стоят не плотнее, чем через 2 м
DURATION_GRACE_MS = 5000
RUN_TTL = timedelta(minutes=30)


class StartResponse(BaseModel):
    run_id: int
    seed: int
    rewarded: bool
    lives: int
    lives_max: int
    next_life_at: Optional[str] = None
    rewarded_runs_left: int


class FinishRequest(BaseModel):
    distance: int = Field(..., ge=0, le=1_000_000)
    coins: int = Field(..., ge=0, le=100_000)
    duration_ms: int = Field(..., ge=0, le=60 * 60 * 1000)


# ---------- Время: «сегодня» и «неделя» в часовом поясе организации ----------

def local_today(now: Optional[datetime] = None) -> date:
    return (now or utcnow()).astimezone(app_timezone()).date()


def day_bounds(day: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day, time.min, tzinfo=app_timezone()).astimezone(timezone.utc)
    return start, start + timedelta(days=1)


def week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


def week_bounds(monday: date) -> tuple[datetime, datetime]:
    start, _ = day_bounds(monday)
    return start, start + timedelta(days=7)


# ---------- Лимиты ----------

async def daily_status(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> Dict[str, int]:
    cfg = settings()
    start, end = day_bounds(local_today(now))
    coins_today = (await db.execute(
        select(func.coalesce(func.sum(GameRun.coins_awarded), 0)).where(
            GameRun.user_id == user_id, GameRun.game == GAME, GameRun.status == "finished",
            GameRun.started_at >= start, GameRun.started_at < end,
        )
    )).scalar() or 0
    return {
        "coins_today": int(coins_today or 0),
        "daily_coin_cap": int(cfg["daily_coin_cap"]),
    }


def coins_for_pickups(pickups: int) -> int:
    cfg = settings()
    return min(math.ceil(pickups / int(cfg["pickups_per_coin"])), int(cfg["max_coins_per_run"]))


def validate_run(run: GameRun, body: FinishRequest, now: datetime) -> Optional[str]:
    """Причина отклонения результата или None"""
    elapsed_ms = (now - as_utc(run.started_at)).total_seconds() * 1000
    if body.duration_ms > elapsed_ms + DURATION_GRACE_MS:
        return "длительность больше реального времени забега"
    if body.distance > MAX_SPEED * (body.duration_ms / 1000) + 20:
        return "слишком большая дистанция для такого времени"
    if body.coins > body.distance / MIN_COIN_SPACING + 10:
        return "монет больше, чем помещается на трассе"
    return None


# ---------- Рейтинг ----------

async def user_group(db: AsyncSession, user_id: int) -> Optional[StudentGroup]:
    row = (await db.execute(
        select(StudentGroup)
        .join(GroupMember, GroupMember.group_id == StudentGroup.id)
        .where(GroupMember.user_id == user_id)
        .order_by(GroupMember.joined_at.desc())
        .limit(1)
    )).scalar_one_or_none()
    return row


async def weekly_board(db: AsyncSession, group_id: Optional[int], monday: date) -> List[Dict[str, object]]:
    """Лучший результат каждого участника за неделю, по убыванию"""
    start, end = week_bounds(monday)
    best = func.max(GameRun.score).label("best")
    query = (
        select(GameRun.user_id, best)
        .where(GameRun.game == GAME, GameRun.status == "finished", GameRun.score > 0,
               GameRun.started_at >= start, GameRun.started_at < end)
        .group_by(GameRun.user_id)
    )
    if group_id is not None:
        members = select(GroupMember.user_id).where(GroupMember.group_id == group_id)
        query = query.where(GameRun.user_id.in_(members))
    rows = (await db.execute(query)).all()
    if not rows:
        return []
    user_ids = [r.user_id for r in rows]
    names = dict((await db.execute(
        select(User.id, func.coalesce(Character.name, User.username))
        .outerjoin(Character, Character.user_id == User.id)
        .where(User.id.in_(user_ids))
    )).all())
    ordered = sorted(rows, key=lambda r: (-int(r.best), r.user_id))
    return [
        {"rank": index + 1, "user_id": r.user_id, "name": names.get(r.user_id) or f"Игрок {r.user_id}", "score": int(r.best)}
        for index, r in enumerate(ordered)
    ]


async def best_score(db: AsyncSession, user_id: int) -> int:
    value = (await db.execute(
        select(func.max(GameRun.score)).where(GameRun.user_id == user_id, GameRun.game == GAME, GameRun.status == "finished")
    )).scalar()
    return int(value or 0)


# ---------- Недельные призы (выдаются лениво при первом запросе новой недели) ----------

async def settle_weekly_prizes(db: AsyncSession, group: StudentGroup, today: Optional[date] = None) -> None:
    prizes: List[int] = settings()["weekly_prizes"]  # type: ignore[assignment]
    if not prizes:
        return
    previous = week_start(today or local_today()) - timedelta(days=7)
    settled = (await db.execute(
        select(func.count(GameWeeklyPrize.id)).where(
            GameWeeklyPrize.game == GAME, GameWeeklyPrize.group_id == group.id, GameWeeklyPrize.week_start == previous
        )
    )).scalar()
    if settled:
        return
    board = (await weekly_board(db, group.id, previous))[: len(prizes)]
    if not board:
        return
    rows = [
        GameWeeklyPrize(game=GAME, group_id=group.id, week_start=previous, user_id=entry["user_id"],
                        place=entry["rank"], score=entry["score"], coins=prizes[entry["rank"] - 1])
        for entry in board
    ]
    db.add_all(rows)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()   # параллельный запрос уже подвёл итоги
        return

    winners = []
    for prize in rows:
        # Атомарно «забираем» приз, чтобы монеты не выдались дважды
        claimed = (await db.execute(
            update(GameWeeklyPrize).where(GameWeeklyPrize.id == prize.id, GameWeeklyPrize.granted_at.is_(None))
            .values(granted_at=utcnow()).returning(GameWeeklyPrize.id)
        )).scalar()
        await db.commit()
        if not claimed:
            continue
        result = await grant_reward({
            "user_id": prize.user_id, "coins": prize.coins, "source": "game_weekly_prize",
            "source_ref": f"runner:{group.id}:{previous.isoformat()}:{prize.place}", "check_unlocks": False,
        })
        if result is None:
            await db.execute(update(GameWeeklyPrize).where(GameWeeklyPrize.id == prize.id).values(granted_at=None))
            await db.commit()
            continue
        entry = next(e for e in board if e["user_id"] == prize.user_id)
        winners.append({"place": prize.place, "user_id": prize.user_id, "name": entry["name"],
                        "score": prize.score, "coins": prize.coins})

    if winners:
        await notify_bot("/notifications/game-weekly-results", {
            "group_name": group.name, "chat_id": group.max_chat_id, "winners": winners,
        })


async def last_prize(db: AsyncSession, user_id: int, today: date) -> Optional[Dict[str, object]]:
    previous = week_start(today) - timedelta(days=7)
    prize = (await db.execute(
        select(GameWeeklyPrize).where(
            GameWeeklyPrize.user_id == user_id, GameWeeklyPrize.game == GAME,
            GameWeeklyPrize.week_start == previous, GameWeeklyPrize.granted_at.is_not(None),
        )
    )).scalar_one_or_none()
    if prize is None:
        return None
    return {"place": prize.place, "coins": prize.coins, "score": prize.score, "week_start": prize.week_start.isoformat()}


# ---------- Эндпоинты ----------

@router.get("/overview")
async def overview(
    user_id: int = Depends(resolve_acting_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Всё для карточки на главном экране: попытки, лимиты, рекорд, место в группе, топ группы"""
    today = local_today()
    group = await user_group(db, user_id)
    if group is not None:
        await settle_weekly_prizes(db, group, today)
    board = await weekly_board(db, group.id if group else None, week_start(today))
    me = next((entry for entry in board if entry["user_id"] == user_id), None)
    lives = lives_snapshot(await load_lives(db, user_id))
    await db.commit()
    return {
        **(await daily_status(db, user_id)),
        **lives,
        "rewarded_runs_left": lives["lives"],
        "rewarded_runs_total": lives["lives_max"],
        "best_score": await best_score(db, user_id),
        "week": {"start": week_start(today).isoformat(), "best": me["score"] if me else 0, "rank": me["rank"] if me else None},
        "scope": "group" if group else "all",
        "group_name": group.name if group else None,
        "players": len(board),
        "top": [{**entry, "is_me": entry["user_id"] == user_id} for entry in board[:5]],
        "weekly_prizes": settings()["weekly_prizes"],
        "last_week_prize": await last_prize(db, user_id, today),
        "score_per_coin": SCORE_PER_COIN,
    }


@router.get("/leaderboard")
async def leaderboard(
    scope: str = Query("group", pattern="^(group|all)$"),
    limit: int = Query(20, ge=1, le=100),
    user_id: int = Depends(resolve_acting_user_id),
    db: AsyncSession = Depends(get_db),
):
    today = local_today()
    group = await user_group(db, user_id) if scope == "group" else None
    board = await weekly_board(db, group.id if group else None, week_start(today))
    me = next((entry for entry in board if entry["user_id"] == user_id), None)
    return {
        "scope": "group" if group else "all",
        "group_name": group.name if group else None,
        "week_start": week_start(today).isoformat(),
        "entries": [{**entry, "is_me": entry["user_id"] == user_id} for entry in board[:limit]],
        "me": me,
        "players": len(board),
    }


@router.post("/start", response_model=StartResponse)
async def start_run(
    user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    if (await db.execute(select(User.id).where(User.id == user_id))).scalar() is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    pending = (await db.execute(
        select(GameRun.id).where(GameRun.user_id == user_id, GameRun.game == GAME, GameRun.status == "started")
    )).scalars().all()
    if pending:
        abandoned = await db.execute(
            update(GameRun)
            .where(GameRun.id.in_(pending), GameRun.status == "started")
            .values(status="abandoned", finished_at=utcnow())
        )
        if abandoned.rowcount:
            await refund_life(db, user_id)
    row = await consume_life(db, user_id)
    if row is None:
        await db.commit()
        raise HTTPException(
            status_code=403,
            detail="Нет попыток. Выполните задачу, получите достижение или дождитесь восстановления жизни.",
        )
    run = GameRun(
        user_id=user_id, game=GAME, seed=secrets.randbelow(2**31 - 1) + 1, rewarded=True,
        status="started", started_at=utcnow(),
    )
    db.add(run)
    await db.commit()
    lives = lives_snapshot(row)
    return StartResponse(
        run_id=run.id, seed=run.seed, rewarded=True,
        lives=lives["lives"], lives_max=lives["lives_max"], next_life_at=lives["next_life_at"],
        rewarded_runs_left=lives["lives"],
    )


@router.post("/runs/{run_id}/finish")
async def finish_run(
    run_id: int,
    body: FinishRequest,
    user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    run = (await db.execute(select(GameRun).where(GameRun.id == run_id))).scalar_one_or_none()
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Забег не найден")
    if run.status != "started":
        raise HTTPException(status_code=409, detail="Результат этого забега уже засчитан")
    now = utcnow()
    if now - as_utc(run.started_at) > RUN_TTL:
        run.status, run.finished_at, run.reject_reason = "rejected", now, "забег устарел"
        await db.commit()
        raise HTTPException(status_code=400, detail="Забег устарел — начните новый")

    previous_best = await best_score(db, user_id)
    reason = validate_run(run, body, now)
    run.finished_at = now
    run.distance, run.coins_collected, run.duration_ms = body.distance, body.coins, body.duration_ms
    if reason:
        run.status, run.reject_reason = "rejected", reason
        await db.commit()
        logger.warning("Забег %s пользователя %s отклонён: %s", run_id, user_id, reason)
        raise HTTPException(status_code=400, detail="Результат не засчитан: похоже на ошибку записи забега")

    run.score = body.distance + body.coins * SCORE_PER_COIN
    status = await daily_status(db, user_id)
    award = 0
    if run.rewarded:
        award = min(coins_for_pickups(body.coins), max(0, status["daily_coin_cap"] - status["coins_today"]))
    run.coins_awarded = award
    run.status = "finished"
    await db.commit()   # HTTP-вызов награды — только после закрытия транзакции

    rewards_status = "none"
    if award > 0:
        result = await grant_reward({
            "user_id": user_id, "coins": award, "source": "minigame",
            "source_ref": f"game_run:{run.id}", "check_unlocks": False,
        })
        if result is None:
            run.coins_awarded, award, rewards_status = 0, 0, "failed"
            await db.commit()
        else:
            rewards_status = "granted"

    today = local_today()
    group = await user_group(db, user_id)
    board = await weekly_board(db, group.id if group else None, week_start(today))
    me = next((entry for entry in board if entry["user_id"] == user_id), None)
    after = await daily_status(db, user_id)
    lives = lives_snapshot(await load_lives(db, user_id))
    await db.commit()
    return {
        "run_id": run.id,
        "score": run.score,
        "distance": run.distance,
        "coins_collected": run.coins_collected,
        "coins_awarded": award,
        "rewarded": run.rewarded,
        "rewards_status": rewards_status,
        "new_record": run.score > previous_best,
        "best_score": max(previous_best, run.score),
        "week": {"best": me["score"] if me else run.score, "rank": me["rank"] if me else None, "players": len(board)},
        "scope": "group" if group else "all",
        "group_name": group.name if group else None,
        "lives": lives["lives"],
        "lives_max": lives["lives_max"],
        "next_life_at": lives["next_life_at"],
        "rewarded_runs_left": lives["lives"],
        "coins_today": after["coins_today"],
        "daily_coin_cap": after["daily_coin_cap"],
    }


@router.post("/runs/{run_id}/abandon")
async def abandon_run(
    run_id: int,
    user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Выход без результата: жизнь возвращается, забег не идёт в рейтинг."""
    result = await db.execute(
        update(GameRun)
        .where(GameRun.id == run_id, GameRun.user_id == user_id, GameRun.status == "started")
        .values(status="abandoned", finished_at=utcnow())
    )
    if not result.rowcount:
        run = (await db.execute(select(GameRun).where(GameRun.id == run_id))).scalar_one_or_none()
        if run is None or run.user_id != user_id:
            raise HTTPException(status_code=404, detail="Забег не найден")
        raise HTTPException(status_code=409, detail="Результат этого забега уже засчитан")
    row = await refund_life(db, user_id)
    await db.commit()
    return {"ok": True, **lives_snapshot(row)}
