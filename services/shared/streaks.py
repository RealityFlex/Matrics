"""
Серия посещений занятий (attendance streak) и «заморозки» (streak freeze).

Счётчик не хранится: серия вычисляется из посещений (lesson_attendances)
и пропусков (lesson_misses), поэтому не рассинхронизируется и учитывает
ручные отметки задним числом.

Правила для завершившихся занятий группы пользователя (в хронологическом порядке):
    attended                   -> серия +1
    frozen / excused / pending -> серия не прерывается (и не растёт)
    penalized                  -> серия сбрасывается
Будущие и идущие занятия без отметки не учитываются.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.models.lesson import (
    Lesson,
    LessonAttendance,
    LessonMiss,
    LessonMissStatus,
    lesson_groups,
)
from services.shared.models.social import GroupMember
from services.shared.timeutil import as_utc, utcnow

ATTENDED = "attended"


def freezes_per_period() -> int:
    try:
        return max(0, int(os.getenv("STREAK_FREEZES_PER_30D", "2")))
    except ValueError:
        return 2


def compute_streaks(statuses: Iterable[str]) -> Tuple[int, int]:
    """Вернуть (текущая серия, лучшая серия) по статусам в хронологическом порядке"""
    current = best = 0
    for status in statuses:
        if status == ATTENDED:
            current += 1
            best = max(best, current)
        elif status == LessonMissStatus.PENALIZED:
            current = 0
        # frozen / excused / pending — не прерывают серию
    return current, best


async def user_lessons_with_membership(db: AsyncSession, user_id: int) -> List[Tuple[Lesson, Optional[datetime]]]:
    """Занятия групп пользователя + дата вступления в группу (самая ранняя из подходящих)"""
    memberships = (await db.execute(
        select(GroupMember.group_id, GroupMember.joined_at).where(GroupMember.user_id == user_id)
    )).all()
    if not memberships:
        return []
    joined_by_group = {group_id: as_utc(joined_at) for group_id, joined_at in memberships}

    rows = (await db.execute(
        select(Lesson, lesson_groups.c.group_id)
        .join(lesson_groups, lesson_groups.c.lesson_id == Lesson.id)
        .where(lesson_groups.c.group_id.in_(list(joined_by_group)))
    )).all()

    lessons: Dict[int, Tuple[Lesson, Optional[datetime]]] = {}
    for lesson, group_id in rows:
        joined = joined_by_group.get(group_id)
        prev = lessons.get(lesson.id)
        if prev is None or (joined is not None and (prev[1] is None or joined < prev[1])):
            lessons[lesson.id] = (lesson, joined)
    return list(lessons.values())


async def load_streak_entries(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
    now = as_utc(now) or utcnow()
    lessons = await user_lessons_with_membership(db, user_id)
    if not lessons:
        return []
    lesson_ids = [lesson.id for lesson, _ in lessons]

    attended_ids = set((await db.execute(
        select(LessonAttendance.lesson_id).where(and_(
            LessonAttendance.user_id == user_id,
            LessonAttendance.lesson_id.in_(lesson_ids),
        ))
    )).scalars().all())

    miss_rows = (await db.execute(
        select(LessonMiss.lesson_id, LessonMiss.status).where(and_(
            LessonMiss.user_id == user_id,
            LessonMiss.lesson_id.in_(lesson_ids),
        ))
    )).all()
    miss_status: Dict[int, str] = {row[0]: row[1] for row in miss_rows}

    entries: List[Dict[str, Any]] = []
    for lesson, joined_at in lessons:
        start = as_utc(lesson.start_time)
        end = as_utc(lesson.end_time)
        if lesson.id in attended_ids:
            status = ATTENDED
        elif end is not None and end < now:
            # Занятия до вступления в группу не считаются пропусками
            if joined_at is not None and start is not None and start < joined_at:
                continue
            status = miss_status.get(lesson.id, LessonMissStatus.PENDING)
        else:
            continue  # будущее или идущее занятие без отметки
        entries.append({"lesson_id": lesson.id, "start_time": start, "status": status})

    entries.sort(key=lambda e: (e["start_time"] is None, e["start_time"]))
    return entries


async def freezes_used(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> int:
    now = as_utc(now) or utcnow()
    since = now - timedelta(days=30)
    return int((await db.execute(
        select(func.count(LessonMiss.id)).where(and_(
            LessonMiss.user_id == user_id,
            LessonMiss.status == LessonMissStatus.FROZEN,
            LessonMiss.resolved_at >= since,
        ))
    )).scalar() or 0)


async def get_attendance_streak(db: AsyncSession, user_id: int, now: Optional[datetime] = None) -> Dict[str, Any]:
    """Серия посещений, лимит «заморозок» и ожидающие решения пропуски"""
    now = as_utc(now) or utcnow()
    entries = await load_streak_entries(db, user_id, now)
    current, best = compute_streaks(e["status"] for e in entries)

    used = await freezes_used(db, user_id, now)
    limit = freezes_per_period()

    pending_rows = (await db.execute(
        select(LessonMiss, Lesson.name)
        .join(Lesson, Lesson.id == LessonMiss.lesson_id)
        .where(and_(LessonMiss.user_id == user_id, LessonMiss.status == LessonMissStatus.PENDING))
        .order_by(LessonMiss.decision_deadline)
    )).all()
    pending = [
        {
            "miss_id": miss.id,
            "lesson_id": miss.lesson_id,
            "lesson_name": name,
            "deadline": as_utc(miss.decision_deadline).isoformat() if miss.decision_deadline else None,
        }
        for miss, name in pending_rows
    ]

    return {
        "current": current,
        "best": best,
        "lessons_attended": sum(1 for e in entries if e["status"] == ATTENDED),
        "freezes_limit": limit,
        "freezes_used_30d": used,
        "freezes_available": max(0, limit - used),
        "pending_misses": pending,
    }
