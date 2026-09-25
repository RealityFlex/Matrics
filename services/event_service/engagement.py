"""
Вовлечённость группы и поддержка:

* командная цель пары — когда отметилось team_goal_percent% группы, все отметившиеся
  получают бонус, а в чат группы MAX приходит сообщение (и итоги пары после её окончания);
* напоминание за 10 минут до пары — в личные сообщения и в чат группы;
* «Нужна помощь?» — студент (или бот по сигналам риска) передаёт обращение куратору.
  Продукт не заменяет специалиста: он лишь быстро связывает студента с ответственным человеком.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import require_verified_user
from services.shared.bot_notify import grant_reward, notify_bot
from services.shared.database import AsyncSessionLocal, get_db
from services.shared.models.character import Character
from services.shared.models.lesson import (
    Lesson,
    LessonAttendance,
    LessonGroupGoal,
    LessonMiss,
    LessonMissStatus,
    SupportRequest,
    lesson_groups,
)
from services.shared.models.social import GroupMember, StudentGroup, group_curators
from services.shared.models.user import User
from services.shared.streaks import get_attendance_streak
from services.shared.timeutil import as_utc, utcnow

logger = logging.getLogger(__name__)
router = APIRouter()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


GROUP_GOAL_BONUS_COINS = _int_env("GROUP_GOAL_BONUS_COINS", 5)
GROUP_GOAL_BONUS_SATISFACTION = _int_env("GROUP_GOAL_BONUS_SATISFACTION", 5)
REMINDER_MINUTES = _int_env("LESSON_REMINDER_MINUTES", 10)
HELP_OFFER_SATISFACTION = _int_env("HELP_OFFER_SATISFACTION", 20)


# ---------- Командная цель ----------

async def group_progress(db: AsyncSession, lesson: Lesson, only_user_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Прогресс групп занятия: сколько отметилось из ожидаемых и достигнута ли цель"""
    start = as_utc(lesson.start_time)
    query = (
        select(StudentGroup)
        .join(lesson_groups, lesson_groups.c.group_id == StudentGroup.id)
        .where(lesson_groups.c.lesson_id == lesson.id)
    )
    if only_user_id is not None:
        query = query.join(GroupMember, GroupMember.group_id == StudentGroup.id).where(GroupMember.user_id == only_user_id)
    groups = (await db.execute(query)).scalars().unique().all()
    if not groups:
        return []

    attended = set((await db.execute(
        select(LessonAttendance.user_id).where(LessonAttendance.lesson_id == lesson.id)
    )).scalars().all())
    goals = {g.group_id: g for g in (await db.execute(
        select(LessonGroupGoal).where(LessonGroupGoal.lesson_id == lesson.id)
    )).scalars()}

    result = []
    for group in groups:
        members = (await db.execute(
            select(GroupMember.user_id, GroupMember.joined_at).where(GroupMember.group_id == group.id)
        )).all()
        expected_ids = [uid for uid, joined in members if joined is None or start is None or as_utc(joined) <= start]
        came = [uid for uid in expected_ids if uid in attended]
        target = group.team_goal_percent or 80
        percent = round(100 * len(came) / len(expected_ids)) if expected_ids else 0
        goal = goals.get(group.id)
        result.append({
            "group_id": group.id,
            "group_name": group.name,
            "attended": len(came),
            "expected": len(expected_ids),
            "percent": percent,
            "target_percent": target,
            "needed": max(0, -(-target * len(expected_ids) // 100) - len(came)),
            "achieved": bool(goal and goal.achieved_at),
            "chat_bound": bool(group.max_chat_id),
            "bonus": {"coins": GROUP_GOAL_BONUS_COINS, "satisfaction": GROUP_GOAL_BONUS_SATISFACTION},
            "_attended_ids": came,
            "_chat_id": group.max_chat_id,
        })
    return result


def public_progress(items: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: v for k, v in item.items() if not k.startswith("_")} for item in items]


async def _goal_row(db: AsyncSession, lesson_id: int, group_id: int) -> LessonGroupGoal:
    row = (await db.execute(select(LessonGroupGoal).where(and_(
        LessonGroupGoal.lesson_id == lesson_id, LessonGroupGoal.group_id == group_id
    )))).scalar_one_or_none()
    if row is None:
        row = LessonGroupGoal(lesson_id=lesson_id, group_id=group_id)
        db.add(row)
    return row


async def process_group_goals(db: AsyncSession, lesson_id: int, user_id: int, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    """
    После отметки студента: обновить прогресс его групп. Если цель достигнута впервые —
    бонус всем отметившимся и сообщение в чат; если уже была достигнута — бонус опоздавшему.
    Возвращает список выданных бонусов (для тестов и логов).
    """
    now = as_utc(now) or utcnow()
    lesson = (await db.execute(select(Lesson).where(Lesson.id == lesson_id))).scalar_one_or_none()
    if lesson is None:
        return []
    progress = await group_progress(db, lesson, only_user_id=user_id)
    bonuses: List[Dict[str, Any]] = []
    chat_messages: List[Dict[str, Any]] = []
    for item in progress:
        row = await _goal_row(db, lesson.id, item["group_id"])
        row.attended, row.expected = item["attended"], item["expected"]
        if row.achieved_at is None and item["expected"] and item["percent"] >= item["target_percent"]:
            row.achieved_at = now
            bonuses.extend({"user_id": uid, "group_id": item["group_id"]} for uid in item["_attended_ids"])
            if item["_chat_id"]:
                chat_messages.append({
                    "chat_id": item["_chat_id"], "group_name": item["group_name"], "lesson_name": lesson.name,
                    "attended": item["attended"], "expected": item["expected"], "percent": item["percent"],
                    "bonus": item["bonus"],
                })
        elif row.achieved_at is not None and user_id in item["_attended_ids"]:
            bonuses.append({"user_id": user_id, "group_id": item["group_id"]})
    await db.commit()

    for bonus in bonuses:
        await grant_reward({
            "user_id": bonus["user_id"],
            "coins": GROUP_GOAL_BONUS_COINS,
            "satisfaction": GROUP_GOAL_BONUS_SATISFACTION,
            "source": "group_goal",
            "source_ref": f"lesson:{lesson.id}:group:{bonus['group_id']}",
            "check_unlocks": False,
        })
    for message in chat_messages:
        await notify_bot("/notifications/group-goal", message)
    return bonuses


async def process_group_goals_background(lesson_id: int, user_id: int) -> None:
    try:
        async with AsyncSessionLocal() as session:
            await process_group_goals(session, lesson_id, user_id)
    except Exception as exc:
        logger.warning("Командная цель не обработана: %s", exc)


async def send_lesson_summaries(db: AsyncSession, now: datetime, tracking_start: datetime) -> int:
    """Итоги закончившейся пары — в чат группы (один раз)"""
    lookback = max(now - timedelta(hours=24), tracking_start)
    lessons = (await db.execute(select(Lesson).where(and_(Lesson.end_time < now, Lesson.end_time > lookback)))).scalars().all()
    messages = []
    for lesson in lessons:
        for item in await group_progress(db, lesson):
            if not item["_chat_id"]:
                continue
            row = await _goal_row(db, lesson.id, item["group_id"])
            if row.summary_sent_at is not None:
                continue
            row.summary_sent_at = now
            row.attended, row.expected = item["attended"], item["expected"]
            streaks = []
            for uid in item["_attended_ids"]:
                streak = await get_attendance_streak(db, uid, now)
                name = (await db.execute(select(User.username).where(User.id == uid))).scalar()
                streaks.append((streak["current"], name))
            streaks.sort(reverse=True)
            messages.append({
                "chat_id": item["_chat_id"], "group_name": item["group_name"], "lesson_name": lesson.name,
                "attended": item["attended"], "expected": item["expected"], "percent": item["percent"],
                "target_percent": item["target_percent"], "achieved": bool(row.achieved_at),
                "top_streaks": [{"name": n, "streak": s} for s, n in streaks[:3] if s > 0],
            })
    await db.commit()
    for message in messages:
        await notify_bot("/notifications/group-lesson-summary", message)
    return len(messages)


# ---------- Напоминания ----------

async def send_lesson_reminders(db: AsyncSession, now: datetime) -> int:
    """За REMINDER_MINUTES до начала — напомнить студентам, ещё не отметившимся, и написать в чат группы"""
    lessons = (await db.execute(select(Lesson).where(and_(
        Lesson.start_time > now,
        Lesson.start_time <= now + timedelta(minutes=REMINDER_MINUTES),
        Lesson.reminder_sent_at.is_(None),
    )))).scalars().all()
    direct: List[Dict[str, Any]] = []
    chats: List[Dict[str, Any]] = []
    for lesson in lessons:
        lesson.reminder_sent_at = now
        payload = {
            "lesson_id": lesson.id, "lesson_name": lesson.name, "location": lesson.location,
            "starts_at": as_utc(lesson.start_time).isoformat(),
            "minutes": max(1, int((as_utc(lesson.start_time) - now).total_seconds() // 60)),
            "is_simulated": bool(lesson.is_simulated),
        }
        for item in await group_progress(db, lesson):
            members = (await db.execute(select(GroupMember.user_id).where(GroupMember.group_id == item["group_id"]))).scalars().all()
            direct.extend({**payload, "user_id": uid} for uid in members if uid not in item["_attended_ids"])
            if item["_chat_id"]:
                chats.append({**payload, "chat_id": item["_chat_id"], "group_name": item["group_name"],
                              "target_percent": item["target_percent"]})
    await db.commit()
    seen = set()
    for message in direct:
        key = (message["user_id"], message["lesson_id"])
        if key not in seen:
            seen.add(key)
            await notify_bot("/notifications/lesson-reminder", message)
    for message in chats:
        await notify_bot("/notifications/group-lesson-reminder", message)
    return len(lessons)


# ---------- «Нужна помощь?» ----------

class SupportRequestIn(BaseModel):
    message: Optional[str] = Field(None, max_length=500)


class InternalSupportRequestIn(SupportRequestIn):
    user_id: int
    source: str = "bot"


async def _curators_for(db: AsyncSession, user_id: int) -> Dict[str, Any]:
    rows = (await db.execute(
        select(StudentGroup.id, StudentGroup.name, group_curators.c.user_id)
        .join(GroupMember, GroupMember.group_id == StudentGroup.id)
        .outerjoin(group_curators, group_curators.c.group_id == StudentGroup.id)
        .where(GroupMember.user_id == user_id)
    )).all()
    return {
        "groups": sorted({name for _, name, _ in rows}),
        "curator_ids": sorted({cid for _, _, cid in rows if cid}),
    }


async def create_support_request(db: AsyncSession, user_id: int, message: Optional[str], source: str) -> Dict[str, Any]:
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    since = utcnow() - timedelta(hours=24)
    existing = (await db.execute(select(SupportRequest).where(and_(
        SupportRequest.user_id == user_id, SupportRequest.status == "open",
        SupportRequest.source.in_(["student", "bot"]), SupportRequest.created_at >= since,
    )))).scalars().first()
    info = await _curators_for(db, user_id)
    if existing is not None:
        return {"id": existing.id, "status": "already_sent", "curators_notified": len(info["curator_ids"])}
    request = SupportRequest(user_id=user_id, source=source, message=message, status="open")
    db.add(request)
    await db.commit()
    await db.refresh(request)
    if info["curator_ids"]:
        await notify_bot("/notifications/support-request", {
            "curator_user_ids": info["curator_ids"], "student_user_id": user_id, "student_name": user.username,
            "groups": info["groups"], "message": message,
        })
    return {"id": request.id, "status": "sent", "curators_notified": len(info["curator_ids"])}


@router.post("/support/request")
async def support_request(
    request: SupportRequestIn,
    user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Студент просит помощи — обращение уходит куратору его группы в MAX"""
    return await create_support_request(db, user_id, request.message, "student")


@router.post("/internal/support/request")
async def internal_support_request(request: InternalSupportRequestIn, db: AsyncSession = Depends(get_db)):
    """Кнопка «Написать куратору» в чат-боте (внутренний вызов, закрыт на gateway)"""
    return await create_support_request(db, request.user_id, request.message, request.source)


async def offer_help_if_needed(db: AsyncSession, user_ids: Iterable[int], now: datetime) -> int:
    """
    Мягкий сигнал поддержки: два штрафных пропуска подряд или очень низкое настроение →
    персонаж предлагает связаться с куратором (не чаще раза в 7 дней).
    """
    offers = []
    for user_id in set(user_ids):
        recent = (await db.execute(select(SupportRequest.id).where(and_(
            SupportRequest.user_id == user_id, SupportRequest.source == "auto_offer",
            SupportRequest.created_at >= now - timedelta(days=7),
        )))).first()
        if recent:
            continue
        last_two = (await db.execute(
            select(LessonMiss.status).join(Lesson, Lesson.id == LessonMiss.lesson_id)
            .where(LessonMiss.user_id == user_id).order_by(Lesson.end_time.desc()).limit(2)
        )).scalars().all()
        satisfaction = (await db.execute(select(Character.satisfaction).where(Character.user_id == user_id))).scalar()
        risky = (len(last_two) == 2 and all(s == LessonMissStatus.PENALIZED for s in last_two)) or (
            satisfaction is not None and satisfaction < HELP_OFFER_SATISFACTION)
        if risky:
            db.add(SupportRequest(user_id=user_id, source="auto_offer", status="offered"))
            offers.append(user_id)
    await db.commit()
    for user_id in offers:
        await notify_bot("/notifications/help-offer", {"user_id": user_id})
    return len(offers)
