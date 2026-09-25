"""
Серия посещений и «день без штрафа» (streak freeze) — мягкая антивыгорательная механика.

Фоновый воркер после окончания занятия фиксирует пропуски (status=pending) и
предлагает студенту в MAX «заморозить» пропуск. Если за отведённое время студент
не воспользовался «заморозкой», пропуск штрафуется: −satisfaction персонажа и сброс серии.
Лимит «заморозок» — STREAK_FREEZES_PER_30D за скользящие 30 дней.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import require_verified_user
from services.shared.database import AsyncSessionLocal, get_db
from services.shared.models.lesson import Lesson, LessonAttendance, LessonMiss, LessonMissStatus, lesson_groups
from services.shared.models.social import GroupMember
from services.shared.streaks import freezes_per_period, freezes_used, get_attendance_streak
from services.shared.timeutil import as_utc, utcnow
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)
router = APIRouter()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


def _tracking_start_default() -> datetime:
    raw = os.getenv("STREAK_TRACKING_START")
    if raw:
        try:
            return as_utc(datetime.fromisoformat(raw))
        except ValueError:
            logger.warning("STREAK_TRACKING_START некорректен: %s", raw)
    return utcnow()


# Пропуски фиксируются только для занятий, закончившихся после старта сервиса:
# иначе первый запуск оштрафовал бы всех студентов за историю.
TRACKING_START = _tracking_start_default()


class FreezeRequest(BaseModel):
    miss_id: int


class InternalFreezeRequest(BaseModel):
    user_id: int


# ---------- Логика ----------

async def freeze_miss(db: AsyncSession, *, user_id: int, miss_id: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    now = as_utc(now) or utcnow()
    miss = (await db.execute(select(LessonMiss).where(LessonMiss.id == miss_id))).scalar_one_or_none()
    if miss is None or miss.user_id != user_id:
        raise HTTPException(status_code=404, detail="Пропуск не найден")
    if miss.status != LessonMissStatus.PENDING:
        raise HTTPException(status_code=409, detail="Этот пропуск уже обработан")
    deadline = as_utc(miss.decision_deadline)
    if deadline is not None and now > deadline:
        raise HTTPException(status_code=409, detail="Время на решение истекло")
    if await freezes_used(db, user_id, now) >= freezes_per_period():
        raise HTTPException(status_code=409, detail="Лимит «дней без штрафа» на 30 дней исчерпан")
    miss.status = LessonMissStatus.FROZEN
    miss.resolved_at = now
    await db.commit()
    streak = await get_attendance_streak(db, user_id, now)
    return {"success": True, "miss_id": miss_id, "status": miss.status, "streak": streak}


async def _notify(endpoint: str, payload: Dict[str, Any]) -> None:
    bot = ServiceClient("max_bot")
    try:
        await bot.post(endpoint, json=payload)
    except Exception as exc:
        logger.warning("Уведомление %s не отправлено: %s", endpoint, exc)
    finally:
        await bot.close()


async def _penalize(user_id: int, penalty: int, lesson_id: int) -> None:
    reward = ServiceClient("reward")
    try:
        await reward.post("/rewards/grant", json={
            "user_id": user_id,
            "satisfaction": -abs(penalty),
            "source": "lesson_missed",
            "source_ref": f"lesson:{lesson_id}",
            "check_unlocks": False,
        })
    except Exception as exc:
        logger.warning("Штраф за пропуск не применён (user=%s, lesson=%s): %s", user_id, lesson_id, exc)
    finally:
        await reward.close()


async def process_lesson_misses(db: AsyncSession, now: Optional[datetime] = None,
                                tracking_start: Optional[datetime] = None) -> Dict[str, int]:
    """Один проход воркера: зафиксировать новые пропуски и применить истёкшие штрафы"""
    now = as_utc(now) or utcnow()
    tracking_start = as_utc(tracking_start) or TRACKING_START
    grace = timedelta(minutes=_int_env("STREAK_MISS_GRACE_MIN", 15))
    decision = timedelta(minutes=_int_env("STREAK_FREEZE_DECISION_MIN", 720))
    penalty = _int_env("MISSED_LESSON_SATISFACTION_PENALTY", 10)
    lookback_start = max(now - timedelta(hours=24), tracking_start)

    created: List[Dict[str, Any]] = []
    lessons = (await db.execute(select(Lesson).where(and_(
        Lesson.end_time < now - grace,
        Lesson.end_time > lookback_start,
    )))).scalars().all()

    for lesson in lessons:
        start = as_utc(lesson.start_time)
        members = (await db.execute(
            select(GroupMember.user_id, GroupMember.joined_at)
            .join(lesson_groups, lesson_groups.c.group_id == GroupMember.group_id)
            .where(lesson_groups.c.lesson_id == lesson.id)
        )).all()
        expected = {uid for uid, joined in members if joined is None or as_utc(joined) <= start}
        if not expected:
            continue
        attended = set((await db.execute(select(LessonAttendance.user_id).where(
            LessonAttendance.lesson_id == lesson.id))).scalars().all())
        already = set((await db.execute(select(LessonMiss.user_id).where(
            LessonMiss.lesson_id == lesson.id))).scalars().all())

        for user_id in sorted(expected - attended - already):
            miss = LessonMiss(
                lesson_id=lesson.id,
                user_id=user_id,
                status=LessonMissStatus.PENDING,
                detected_at=now,
                decision_deadline=now + decision,
            )
            db.add(miss)
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                continue
            await db.refresh(miss)
            created.append({"miss": miss, "lesson": lesson})

    notifications = []
    for item in created:
        miss, lesson = item["miss"], item["lesson"]
        available = max(0, freezes_per_period() - await freezes_used(db, miss.user_id, now))
        notifications.append({
            "user_id": miss.user_id,
            "miss_id": miss.id,
            "lesson_id": lesson.id,
            "lesson_name": lesson.name,
            "deadline": as_utc(miss.decision_deadline).isoformat(),
            "freezes_available": available,
            "penalty": penalty,
        })
    # HTTP-вызовы — только при закрытой транзакции, чтобы не держать блокировки
    await db.commit()
    for payload in notifications:
        await _notify("/notifications/lesson-missed", payload)

    expired = (await db.execute(select(LessonMiss).where(and_(
        LessonMiss.status == LessonMissStatus.PENDING,
        LessonMiss.decision_deadline < now,
    )))).scalars().all()
    for miss in expired:
        miss.status = LessonMissStatus.PENALIZED
        miss.resolved_at = now
        miss.satisfaction_penalty = penalty
    to_penalize = [(miss.user_id, miss.lesson_id) for miss in expired]
    await db.commit()
    for user_id, lesson_id in to_penalize:
        await _penalize(user_id, penalty, lesson_id)

    return {"created": len(created), "penalized": len(expired),
            "penalized_users": sorted({user_id for user_id, _ in to_penalize})}


async def lesson_miss_worker() -> None:
    from services.event_service.engagement import offer_help_if_needed, send_lesson_reminders, send_lesson_summaries

    # Раз в минуту: напоминания перед парой, пропуски, итоги пар в чаты групп, сигналы поддержки
    interval = max(30, _int_env("STREAK_WORKER_INTERVAL_S", 60))
    logger.info("Воркер пропусков запущен (интервал %s с, учёт с %s)", interval, TRACKING_START.isoformat())
    while True:
        try:
            async with AsyncSessionLocal() as session:
                now = utcnow()
                reminders = await send_lesson_reminders(session, now)
                result = await process_lesson_misses(session, now=now)
                summaries = await send_lesson_summaries(session, now, TRACKING_START)
                offers = await offer_help_if_needed(session, result["penalized_users"], now)
                if reminders or result["created"] or result["penalized"] or summaries or offers:
                    logger.info("Воркер: напоминаний %s, пропусков %s, штрафов %s, итогов %s, предложений помощи %s",
                                reminders, result["created"], result["penalized"], summaries, offers)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Ошибка воркера пропусков: %s", exc)
        await asyncio.sleep(interval)


# ---------- Эндпоинты ----------

@router.get("/streaks/users/{user_id}")
async def get_streak(user_id: int, db: AsyncSession = Depends(get_db)):
    """Серия посещений, остаток «дней без штрафа» и пропуски, ожидающие решения"""
    return await get_attendance_streak(db, user_id)


@router.post("/streaks/users/{user_id}/freeze")
async def use_freeze(
    user_id: int,
    request: FreezeRequest,
    acting_user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Взять «день без штрафа» для пропуска"""
    if acting_user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя использовать «заморозку» за другого пользователя")
    return await freeze_miss(db, user_id=user_id, miss_id=request.miss_id)


@router.post("/internal/streaks/misses/{miss_id}/freeze")
async def internal_freeze(miss_id: int, request: InternalFreezeRequest, db: AsyncSession = Depends(get_db)):
    """«Заморозка» по кнопке в чат-боте (внутренний вызов, закрыт на gateway)"""
    return await freeze_miss(db, user_id=request.user_id, miss_id=miss_id)
