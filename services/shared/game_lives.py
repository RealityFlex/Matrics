"""
Жизни мини-игры: тратятся на забег, выдаются за учёбу, восстанавливаются по таймеру.

Задумка: забег — редкая награда за дисциплину, а не бесконечное развлечение.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.models.minigame import GameLives
from services.shared.timeutil import as_utc, utcnow

LIFE_SOURCES = {
    "task_completion": 1,
    "habit_completion": 1,
    "lesson_attendance": 1,
    "achievement": 1,
}


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def lives_max() -> int:
    return max(1, _int_env("GAME_LIVES_MAX", 3))


def lives_start() -> int:
    return max(0, min(lives_max(), _int_env("GAME_LIVES_START", 0)))


def regen_interval() -> timedelta:
    minutes = max(1, _int_env("GAME_LIFE_REGEN_MINUTES", 120))
    return timedelta(minutes=minutes)


def apply_regen(row: GameLives, now: datetime) -> GameLives:
    cap = lives_max()
    if row.lives >= cap:
        return row
    last = as_utc(row.last_regen_at) or now
    interval = regen_interval()
    gained = int((now - last) // interval)
    if gained <= 0:
        return row
    row.lives = min(cap, row.lives + gained)
    if row.lives >= cap:
        row.last_regen_at = now
    else:
        row.last_regen_at = last + gained * interval
    return row


def snapshot(row: GameLives, now: Optional[datetime] = None) -> Dict[str, Any]:
    moment = now or utcnow()
    cap = lives_max()
    next_at = None
    if row.lives < cap:
        last = as_utc(row.last_regen_at) or moment
        next_at = (last + regen_interval()).isoformat()
    return {
        "lives": int(row.lives),
        "lives_max": cap,
        "next_life_at": next_at,
        "regen_minutes": int(regen_interval().total_seconds() // 60),
    }


async def load_lives(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> GameLives:
    moment = now or utcnow()
    row = (await db.execute(select(GameLives).where(GameLives.user_id == user_id))).scalar_one_or_none()
    if row is None:
        row = GameLives(user_id=user_id, lives=lives_start(), last_regen_at=moment)
        db.add(row)
        await db.flush()
        return row
    apply_regen(row, moment)
    return row


async def add_lives(db: AsyncSession, user_id: int, amount: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    moment = now or utcnow()
    row = await load_lives(db, user_id, moment)
    added = 0
    if amount > 0 and row.lives < lives_max():
        before = row.lives
        row.lives = min(lives_max(), row.lives + amount)
        added = row.lives - before
        if row.lives >= lives_max():
            row.last_regen_at = moment
    await db.commit()
    await db.refresh(row)
    result = snapshot(row, moment)
    result["lives_added"] = added
    return result


async def consume_life(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> Optional[GameLives]:
    moment = now or utcnow()
    row = await load_lives(db, user_id, moment)
    if row.lives < 1:
        return None
    was_full = row.lives >= lives_max()
    row.lives -= 1
    if was_full:
        row.last_regen_at = moment
    return row


async def refund_life(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> GameLives:
    moment = now or utcnow()
    row = await load_lives(db, user_id, moment)
    if row.lives < lives_max():
        row.lives += 1
        if row.lives >= lives_max():
            row.last_regen_at = moment
    return row


def lives_for_source(source: Optional[str]) -> int:
    if not source:
        return 0
    return LIFE_SOURCES.get(source, 0)
