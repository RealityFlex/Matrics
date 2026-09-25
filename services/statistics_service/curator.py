"""
Дашборд куратора / преподавателя: read-only витрина поверх существующих данных
(посещения занятий, пропуски, снимки параметров персонажей, журнал наград).
Отдельная роль: куратор (users.role=curator, группы в group_curators) через MAX
или администратор по токену.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import StaffContext, require_admin, require_staff
from services.shared.bot_notify import notify_bot
from services.shared.database import get_db
from services.shared.models.character import Character, CharacterSnapshot
from services.shared.models.economy import Transaction
from services.shared.models.lesson import Lesson, LessonAttendance, LessonMiss, LessonMissStatus, SupportRequest, lesson_groups
from services.shared.models.social import GroupMember, StudentGroup, group_curators
from services.shared.models.user import User
from services.shared.streaks import get_attendance_streak
from services.shared.timeutil import as_utc, utcnow

router = APIRouter()
LOW_SATISFACTION = 30


def _check_scope(staff: StaffContext, group_id: int) -> None:
    if not staff.can_view_group(group_id):
        raise HTTPException(status_code=403, detail="Нет доступа к этой группе")


async def _group_or_404(db: AsyncSession, group_id: int) -> StudentGroup:
    group = (await db.execute(select(StudentGroup).where(StudentGroup.id == group_id))).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return group


async def _members(db: AsyncSession, group_id: int) -> List[Dict[str, Any]]:
    rows = (await db.execute(
        select(User.id, User.username, GroupMember.joined_at, Character.satisfaction, Character.intelligence_level)
        .join(GroupMember, GroupMember.user_id == User.id)
        .outerjoin(Character, Character.user_id == User.id)
        .where(GroupMember.group_id == group_id)
        .order_by(User.username)
    )).all()
    return [
        {"user_id": r[0], "username": r[1], "joined_at": as_utc(r[2]), "satisfaction": r[3],
         "intelligence_level": r[4]}
        for r in rows
    ]


async def _ended_lessons(db: AsyncSession, group_id: int, date_from: Optional[datetime] = None,
                         date_to: Optional[datetime] = None) -> List[Lesson]:
    now = utcnow()
    conditions = [lesson_groups.c.group_id == group_id, Lesson.end_time < now]
    if date_from:
        conditions.append(Lesson.start_time >= date_from)
    if date_to:
        conditions.append(Lesson.start_time <= date_to)
    lessons = (await db.execute(
        select(Lesson).join(lesson_groups, lesson_groups.c.lesson_id == Lesson.id).where(and_(*conditions))
    )).scalars().all()
    return sorted(lessons, key=lambda l: as_utc(l.start_time))


async def _attendance_map(db: AsyncSession, lesson_ids: List[int]) -> Dict[int, set]:
    result: Dict[int, set] = defaultdict(set)
    if not lesson_ids:
        return result
    rows = (await db.execute(
        select(LessonAttendance.lesson_id, LessonAttendance.user_id).where(LessonAttendance.lesson_id.in_(lesson_ids))
    )).all()
    for lesson_id, user_id in rows:
        result[lesson_id].add(user_id)
    return result


def _expected(member: Dict[str, Any], lesson: Lesson) -> bool:
    joined = member["joined_at"]
    return joined is None or joined <= as_utc(lesson.start_time)


@router.get("/stats/curator/groups")
async def curator_groups(staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """Группы, доступные куратору (администратору — все)"""
    query = select(StudentGroup).order_by(StudentGroup.name)
    if staff.group_ids is not None:
        query = query.where(StudentGroup.id.in_(staff.group_ids or [0]))
    groups = (await db.execute(query)).scalars().all()
    result = []
    for group in groups:
        count = len((await db.execute(select(GroupMember.id).where(GroupMember.group_id == group.id))).all())
        result.append({"id": group.id, "name": group.name, "description": group.description, "members": count})
    return {"role": staff.role, "groups": result}


@router.get("/stats/curator/groups/{group_id}/attendance")
async def group_attendance(
    group_id: int,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    staff: StaffContext = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """Посещаемость группы за период: по занятиям и по студентам (только завершившиеся занятия)"""
    _check_scope(staff, group_id)
    group = await _group_or_404(db, group_id)
    date_from = as_utc(date_from) or (utcnow() - timedelta(days=30))
    date_to = as_utc(date_to)
    members = await _members(db, group_id)
    lessons = await _ended_lessons(db, group_id, date_from, date_to)
    attendance = await _attendance_map(db, [l.id for l in lessons])

    per_lesson = []
    total_expected = total_attended = 0
    for lesson in lessons:
        expected = [m for m in members if _expected(m, lesson)]
        attended = sum(1 for m in expected if m["user_id"] in attendance[lesson.id])
        total_expected += len(expected)
        total_attended += attended
        per_lesson.append({
            "lesson_id": lesson.id, "name": lesson.name, "start_time": as_utc(lesson.start_time).isoformat(),
            "expected": len(expected), "attended": attended,
            "rate": round(attended / len(expected), 3) if expected else None,
            "is_simulated": bool(lesson.is_simulated),
        })

    per_student = []
    for member in members:
        expected_count = attended_count = 0
        for lesson in lessons:
            if not _expected(member, lesson):
                continue
            expected_count += 1
            if member["user_id"] in attendance[lesson.id]:
                attended_count += 1
        # Серия — тем же расчётом, что видит студент (с учётом «дней без штрафа»)
        current = (await get_attendance_streak(db, member["user_id"]))["current"]
        per_student.append({
            "user_id": member["user_id"], "username": member["username"],
            "attended": attended_count, "expected": expected_count,
            "rate": round(attended_count / expected_count, 3) if expected_count else None,
            "current_streak": current, "satisfaction": member["satisfaction"],
        })

    return {
        "group": {"id": group.id, "name": group.name},
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat() if date_to else None},
        "lessons_total": len(lessons),
        "members_total": len(members),
        "attendance_rate": round(total_attended / total_expected, 3) if total_expected else None,
        "per_lesson": per_lesson,
        "per_student": per_student,
    }


@router.get("/stats/curator/groups/{group_id}/at-risk")
async def group_at_risk(
    group_id: int,
    days: int = 7,
    drop_threshold: int = 15,
    staff: StaffContext = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """
    Студенты с риском потери вовлечённости: падение satisfaction за `days` дней,
    низкое satisfaction, низкая посещаемость за 14 дней, недавний штраф за пропуск.
    """
    _check_scope(staff, group_id)
    await _group_or_404(db, group_id)
    members = await _members(db, group_id)
    user_ids = [m["user_id"] for m in members]
    today = utcnow().date()
    since = today - timedelta(days=days)

    snapshots: Dict[int, CharacterSnapshot] = {}
    if user_ids:
        rows = (await db.execute(
            select(CharacterSnapshot).where(and_(
                CharacterSnapshot.user_id.in_(user_ids),
                CharacterSnapshot.snapshot_date <= since,
            )).order_by(CharacterSnapshot.snapshot_date.desc())
        )).scalars().all()
        for snap in rows:
            snapshots.setdefault(snap.user_id, snap)

    lessons = await _ended_lessons(db, group_id, utcnow() - timedelta(days=14))
    attendance = await _attendance_map(db, [l.id for l in lessons])
    penalties = set()
    if user_ids:
        penalties = set((await db.execute(select(LessonMiss.user_id).where(and_(
            LessonMiss.user_id.in_(user_ids),
            LessonMiss.status == LessonMissStatus.PENALIZED,
            LessonMiss.resolved_at >= utcnow() - timedelta(days=days),
        )))).scalars().all())

    asked_help = set()
    if user_ids:
        asked_help = set((await db.execute(select(SupportRequest.user_id).where(and_(
            SupportRequest.user_id.in_(user_ids), SupportRequest.status == "open",
            SupportRequest.source.in_(["student", "bot"]),
        )))).scalars().all())

    result = []
    for member in members:
        flags = []
        severity = 0
        if member["user_id"] in asked_help:
            flags.append("asked_help")
            severity += 3
        current = member["satisfaction"]
        baseline = snapshots.get(member["user_id"])
        drop = None
        if current is not None and baseline is not None:
            drop = baseline.satisfaction - current
            if drop >= drop_threshold:
                flags.append("satisfaction_drop")
                severity += 2
        if current is not None and current < LOW_SATISFACTION:
            flags.append("low_satisfaction")
            severity += 2
        expected = [l for l in lessons if _expected(member, l)]
        if expected:
            rate = sum(1 for l in expected if member["user_id"] in attendance[l.id]) / len(expected)
            if rate < 0.6:
                flags.append("low_attendance_14d")
                severity += 1
        else:
            rate = None
        if member["user_id"] in penalties:
            flags.append("recent_penalty")
            severity += 1
        if flags:
            result.append({
                "user_id": member["user_id"], "username": member["username"], "satisfaction": current,
                "satisfaction_drop": drop, "attendance_rate_14d": round(rate, 3) if rate is not None else None,
                "flags": flags, "severity": severity,
            })
    # Обращения «Нужна помощь» — всегда первыми, затем по тяжести сигналов
    result.sort(key=lambda r: ("asked_help" not in r["flags"], -r["severity"],
                               r["satisfaction"] if r["satisfaction"] is not None else 100))
    return {"group_id": group_id, "days": days, "students": result,
            "note": "Сигнал для куратора, а не диагноз: сложные случаи передаются специалисту."}


def _week_start(day: date) -> date:
    return day - timedelta(days=day.weekday())


@router.get("/stats/curator/groups/{group_id}/weekly")
async def group_weekly(
    group_id: int,
    weeks: int = 8,
    staff: StaffContext = Depends(require_staff),
    db: AsyncSession = Depends(get_db),
):
    """Динамика группы по неделям: посещаемость, среднее satisfaction, активные студенты, заработанные монеты"""
    _check_scope(staff, group_id)
    await _group_or_404(db, group_id)
    weeks = max(1, min(weeks, 26))
    members = await _members(db, group_id)
    user_ids = [m["user_id"] for m in members]
    first_week = _week_start(utcnow().date()) - timedelta(weeks=weeks - 1)
    start_dt = datetime.combine(first_week, datetime.min.time()).replace(tzinfo=utcnow().tzinfo)

    buckets: Dict[date, Dict[str, Any]] = {
        first_week + timedelta(weeks=i): {"expected": 0, "attended": 0, "sat": [], "active": set(), "coins": 0}
        for i in range(weeks)
    }

    lessons = await _ended_lessons(db, group_id, start_dt)
    attendance = await _attendance_map(db, [l.id for l in lessons])
    for lesson in lessons:
        bucket = buckets.get(_week_start(as_utc(lesson.start_time).date()))
        if bucket is None:
            continue
        for member in members:
            if _expected(member, lesson):
                bucket["expected"] += 1
                if member["user_id"] in attendance[lesson.id]:
                    bucket["attended"] += 1
                    bucket["active"].add(member["user_id"])

    if user_ids:
        snaps = (await db.execute(select(CharacterSnapshot).where(and_(
            CharacterSnapshot.user_id.in_(user_ids), CharacterSnapshot.snapshot_date >= first_week
        )))).scalars().all()
        for snap in snaps:
            bucket = buckets.get(_week_start(snap.snapshot_date))
            if bucket is not None:
                bucket["sat"].append(snap.satisfaction)
        txs = (await db.execute(select(Transaction.created_at, Transaction.amount).where(and_(
            Transaction.user_id.in_(user_ids), Transaction.source.isnot(None), Transaction.created_at >= start_dt
        )))).all()
        for created_at, amount in txs:
            if created_at is None:
                continue
            bucket = buckets.get(_week_start(as_utc(created_at).date()))
            if bucket is not None and amount > 0:
                bucket["coins"] += amount

    return {
        "group_id": group_id,
        "weeks": [
            {
                "week_start": week.isoformat(),
                "attendance_rate": round(b["attended"] / b["expected"], 3) if b["expected"] else None,
                "avg_satisfaction": round(sum(b["sat"]) / len(b["sat"]), 1) if b["sat"] else None,
                "active_students": len(b["active"]),
                "coins_earned": b["coins"],
            }
            for week, b in sorted(buckets.items())
        ],
    }



# ---------- Кабинет куратора в MAX ----------

async def _require_member(db: AsyncSession, staff: StaffContext, user_id: int) -> None:
    groups = (await db.execute(select(GroupMember.group_id).where(GroupMember.user_id == user_id))).scalars().all()
    if not groups:
        raise HTTPException(status_code=404, detail="Студент не состоит в учебных группах")
    if staff.group_ids is not None and not set(groups) & set(staff.group_ids):
        raise HTTPException(status_code=403, detail="Студент не из ваших групп")


@router.get("/stats/curator/groups/{group_id}/lessons")
async def group_lessons_today(group_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """Пары группы: идущая сейчас и ближайшие (для кнопки «Показать QR» в кабинете куратора)"""
    _check_scope(staff, group_id)
    now = utcnow()
    lessons = (await db.execute(
        select(Lesson).join(lesson_groups, lesson_groups.c.lesson_id == Lesson.id)
        .where(and_(lesson_groups.c.group_id == group_id, Lesson.end_time >= now - timedelta(minutes=15),
                    Lesson.start_time <= now + timedelta(days=2)))
    )).scalars().all()
    lessons = sorted(lessons, key=lambda l: as_utc(l.start_time))
    attended = await _attendance_map(db, [l.id for l in lessons])
    members = await _members(db, group_id)
    return [{
        "id": l.id, "name": l.name, "location": l.location,
        "start_time": as_utc(l.start_time).isoformat(), "end_time": as_utc(l.end_time).isoformat(),
        "is_now": as_utc(l.start_time) - timedelta(minutes=15) <= now <= as_utc(l.end_time) + timedelta(minutes=15),
        "attended": len([m for m in members if m["user_id"] in attended[l.id]]),
        "expected": len([m for m in members if _expected(m, l)]),
        "is_simulated": bool(l.is_simulated),
    } for l in lessons]


@router.post("/stats/curator/students/{user_id}/nudge")
async def nudge_student(user_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """«Написать студенту»: бот мягко спрашивает, всё ли в порядке, и предлагает помощь"""
    await _require_member(db, staff, user_id)
    curator_name = None
    if staff.user_id:
        curator_name = (await db.execute(select(User.username).where(User.id == staff.user_id))).scalar()
    db.add(SupportRequest(user_id=user_id, source="curator_nudge", status="offered"))
    await db.commit()
    delivered = await notify_bot("/notifications/curator-nudge", {"user_id": user_id, "curator_name": curator_name})
    return {"success": True, "delivered": delivered}


@router.get("/stats/curator/groups/{group_id}/support")
async def group_support_requests(group_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """Открытые обращения «Нужна помощь» студентов группы"""
    _check_scope(staff, group_id)
    rows = (await db.execute(
        select(SupportRequest, User.username)
        .join(User, User.id == SupportRequest.user_id)
        .join(GroupMember, GroupMember.user_id == SupportRequest.user_id)
        .where(and_(GroupMember.group_id == group_id, SupportRequest.status == "open",
                    SupportRequest.source.in_(["student", "bot"])))
        .order_by(SupportRequest.created_at.desc())
    )).all()
    return [{"id": r.id, "user_id": r.user_id, "username": name, "message": r.message,
             "created_at": as_utc(r.created_at).isoformat() if r.created_at else None} for r, name in rows]


@router.post("/stats/curator/support/{request_id}/resolve")
async def resolve_support_request(request_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    request = (await db.execute(select(SupportRequest).where(SupportRequest.id == request_id))).scalar_one_or_none()
    if request is None:
        raise HTTPException(status_code=404, detail="Обращение не найдено")
    await _require_member(db, staff, request.user_id)
    request.status = "resolved"
    request.resolved_at = utcnow()
    await db.commit()
    return {"success": True}


async def build_curator_digests(db: AsyncSession) -> List[Dict[str, Any]]:
    """Сводка для каждого куратора: посещаемость групп за 7 дней и студенты в зоне риска"""
    rows = (await db.execute(
        select(group_curators.c.user_id, StudentGroup).join(StudentGroup, StudentGroup.id == group_curators.c.group_id)
    )).all()
    by_curator: Dict[int, List[StudentGroup]] = defaultdict(list)
    for curator_id, group in rows:
        by_curator[curator_id].append(group)
    staff = StaffContext(role="admin")
    digests = []
    for curator_id, groups in by_curator.items():
        items = []
        for group in groups:
            attendance = await group_attendance(group.id, utcnow() - timedelta(days=7), None, staff, db)
            risk = await group_at_risk(group.id, 7, 15, staff, db)
            items.append({
                "group_id": group.id, "group_name": group.name,
                "attendance_rate": attendance["attendance_rate"], "lessons_total": attendance["lessons_total"],
                "at_risk": [{"username": s["username"], "flags": s["flags"]} for s in risk["students"][:5]],
            })
        digests.append({"curator_user_id": curator_id, "groups": items})
    return digests


@router.post("/stats/curator/digest/send", dependencies=[Depends(require_admin)])
async def send_curator_digests(db: AsyncSession = Depends(get_db)):
    """Отправить еженедельную сводку кураторам сейчас (для демонстрации; по расписанию — по понедельникам)"""
    digests = await build_curator_digests(db)
    await db.commit()
    delivered = 0
    for digest in digests:
        delivered += int(await notify_bot("/notifications/curator-digest", digest))
    return {"curators": len(digests), "delivered": delivered}


async def digest_worker() -> None:
    """Раз в час проверяет: понедельник, 9:00+ по времени организации и сводка на этой неделе ещё не ушла"""
    import asyncio
    import logging

    from services.shared.database import AsyncSessionLocal
    from services.shared.timeutil import app_timezone

    log = logging.getLogger(__name__)
    sent_week = None
    while True:
        try:
            local = utcnow().astimezone(app_timezone())
            week = local.isocalendar()[:2]
            if local.weekday() == 0 and local.hour >= 9 and week != sent_week:
                async with AsyncSessionLocal() as session:
                    digests = await build_curator_digests(session)
                for digest in digests:
                    await notify_bot("/notifications/curator-digest", digest)
                sent_week = week
                log.info("Еженедельная сводка отправлена кураторам: %s", len(digests))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("Сводка кураторам не отправлена: %s", exc)
        await asyncio.sleep(3600)
