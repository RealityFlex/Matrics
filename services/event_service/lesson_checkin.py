"""
Отметка на занятии — основной сценарий продукта.

Студент отмечается ротируемым кодом (вводит вручную, сканирует QR через
openCodeReader или открывает QR-диплинк на мини-приложение MAX) →
Reward Service начисляет монеты, интеллект и удовлетворение →
в ответе возвращается состояние персонажа для анимации →
в фоне бот MAX отправляет уведомление, а WebSocket — событие attendance.confirmed.
"""
from __future__ import annotations

import io
import logging
import os
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Deque, Dict, List, Optional, Tuple

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from services.shared import attendance_codes as codes
from services.shared.auth import StaffContext, require_admin, require_staff, require_verified_user
from services.shared.database import get_db
from services.shared.models.lesson import Lesson, LessonAttendance, VerificationMethod, lesson_groups
from services.shared.models.social import GroupMember
from services.shared.models.user import User
from services.shared.realtime import push_user_event
from services.shared.streaks import get_attendance_streak
from services.shared.timeutil import app_timezone, as_utc, utcnow
from services.shared.utils import ServiceClient
from services.event_service.engagement import group_progress, process_group_goals_background, public_progress

logger = logging.getLogger(__name__)
router = APIRouter()

# Допуск для окна занятия: отметиться можно за 15 минут до начала и 15 минут после конца
CHECKIN_MARGIN = timedelta(minutes=15)
# Ограничение перебора кода: не более 5 ошибок за 10 минут на пару (пользователь, занятие)
MAX_FAILED_ATTEMPTS = 5
FAILED_WINDOW_SECONDS = 600
_failed_attempts: Dict[Tuple[int, int], Deque[float]] = defaultdict(deque)


def _utcnow() -> datetime:
    """Отдельная функция, чтобы тесты могли подменять текущее время"""
    return utcnow()


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def bot_username() -> str:
    return os.getenv("MAX_BOT_USERNAME", "").strip().lstrip("@")


# ---------- Схемы ----------

class CheckInRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=4, description="4-значный код с экрана преподавателя")
    method: str = Field("code", description="code — ввод вручную, qr — скан QR / диплинк")


class InternalCheckInRequest(CheckInRequest):
    user_id: int


class ManualAttendanceRequest(BaseModel):
    user_id: int


class LessonQRResponse(BaseModel):
    lesson_id: int
    code: str
    qr_token: str = Field(..., description="То же, что code (совместимость со старой админкой)")
    expires_in_seconds: int
    window_seconds: int
    payload: str
    deep_link: Optional[str] = None
    bot_link: Optional[str] = None
    qr_code_data: str


class CheckInResponse(BaseModel):
    status: str  # checked_in | already
    message: str
    lesson: Dict[str, Any]
    attendance_id: Optional[int] = None
    verification_method: Optional[str] = None
    rewards: Optional[Dict[str, int]] = None
    rewards_status: str = "none"  # granted | pending | none
    character: Optional[Dict[str, Any]] = None
    streak: Dict[str, Any] = {}
    unlocked_sets: List[Dict[str, Any]] = []
    achievements_earned: List[Any] = []
    # Командная цель группы на этой паре (прогресс после отметки)
    group_goal: Optional[Dict[str, Any]] = None


# ---------- Вспомогательные функции ----------

def _register_failure(user_id: int, lesson_id: int) -> None:
    _failed_attempts[(user_id, lesson_id)].append(time.monotonic())


def _check_rate_limit(user_id: int, lesson_id: int) -> None:
    attempts = _failed_attempts[(user_id, lesson_id)]
    border = time.monotonic() - FAILED_WINDOW_SECONDS
    while attempts and attempts[0] < border:
        attempts.popleft()
    if len(attempts) >= MAX_FAILED_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Слишком много неверных попыток. Подождите несколько минут.")


async def _load_lesson(db: AsyncSession, lesson_id: int) -> Lesson:
    result = await db.execute(select(Lesson).options(selectinload(Lesson.groups)).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")
    return lesson


async def ensure_lesson_secret(db: AsyncSession, lesson: Lesson) -> str:
    if not lesson.qr_secret:
        lesson.qr_secret = codes.new_secret()
        await db.commit()
        await db.refresh(lesson)
    return lesson.qr_secret


def lesson_brief(lesson: Lesson) -> Dict[str, Any]:
    return {
        "id": lesson.id,
        "name": lesson.name,
        "location": lesson.location,
        "start_time": as_utc(lesson.start_time).isoformat() if lesson.start_time else None,
        "end_time": as_utc(lesson.end_time).isoformat() if lesson.end_time else None,
        "reward_coins": lesson.reward_coins,
        "reward_intelligence_points": lesson.reward_intelligence_points,
        "reward_satisfaction": lesson.reward_satisfaction,
        "is_simulated": bool(lesson.is_simulated),
    }


async def _grant_lesson_rewards(lesson: Lesson, user_id: int) -> Optional[Dict[str, Any]]:
    reward_service = ServiceClient("reward")
    try:
        return await reward_service.post("/rewards/grant", json={
            "user_id": user_id,
            "coins": lesson.reward_coins,
            "intelligence_points": lesson.reward_intelligence_points,
            "satisfaction": lesson.reward_satisfaction,
            "source": "lesson_attendance",
            "source_ref": f"lesson:{lesson.id}",
        })
    except Exception as exc:
        logger.error("Награда за занятие %s пользователю %s не выдана: %s", lesson.id, user_id, exc)
        return None
    finally:
        await reward_service.close()


async def _attendance_side_effects(user_id: int, payload: Dict[str, Any]) -> None:
    """Уведомление в MAX и realtime-событие во фронтенд (в фоне, после ответа)"""
    bot = ServiceClient("max_bot")
    try:
        await bot.post("/notifications/attendance-confirmed", json={"user_id": user_id, **payload})
    except Exception as exc:
        logger.warning("Уведомление об отметке не отправлено в MAX: %s", exc)
    finally:
        await bot.close()
    await push_user_event(user_id, "attendance.confirmed", payload=payload)


# ---------- Ядро ----------

async def perform_lesson_check_in(
    db: AsyncSession,
    *,
    lesson_id: int,
    user_id: int,
    code: Optional[str],
    method: VerificationMethod,
    background: Optional[BackgroundTasks],
    skip_code: bool = False,
    now: Optional[datetime] = None,
) -> CheckInResponse:
    now = as_utc(now) or _utcnow()
    lesson = await _load_lesson(db, lesson_id)

    if (await db.execute(select(User.id).where(User.id == user_id))).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if not skip_code:
        _check_rate_limit(user_id, lesson_id)
        if not codes.verify_lesson_code(lesson.qr_secret, lesson.id, code, now):
            _register_failure(user_id, lesson_id)
            raise HTTPException(
                status_code=400,
                detail="Неверный или устаревший код. Введите код, который сейчас на экране преподавателя.",
            )

        if _env_flag("CHECKIN_ENFORCE_WINDOW", "true"):
            start, end = as_utc(lesson.start_time), as_utc(lesson.end_time)
            if start and end and not (start - CHECKIN_MARGIN <= now <= end + CHECKIN_MARGIN):
                raise HTTPException(status_code=400, detail="Отметиться можно только во время занятия")

        group_ids = [g.id for g in lesson.groups]
        if not group_ids:
            raise HTTPException(status_code=400, detail="Занятие не привязано к учебной группе")
        member = await db.execute(select(GroupMember.id).where(and_(
            GroupMember.group_id.in_(group_ids), GroupMember.user_id == user_id
        )))
        if member.first() is None:
            raise HTTPException(status_code=403, detail="Вы не состоите в группе этого занятия")

    existing = (await db.execute(select(LessonAttendance).where(and_(
        LessonAttendance.lesson_id == lesson_id, LessonAttendance.user_id == user_id
    )))).scalar_one_or_none()
    if existing is not None:
        return CheckInResponse(
            status="already",
            message="Вы уже отмечены на этом занятии",
            lesson=lesson_brief(lesson),
            attendance_id=existing.id,
            verification_method=existing.verification_method.value if existing.verification_method else None,
            rewards_status="granted" if existing.rewards_granted_at else "none",
            streak=await get_attendance_streak(db, user_id, now),
        )

    attendance = LessonAttendance(lesson_id=lesson_id, user_id=user_id, verification_method=method)
    db.add(attendance)
    try:
        await db.commit()
    except IntegrityError:
        # Параллельная отметка того же пользователя: награда уже выдана первым запросом
        await db.rollback()
        return CheckInResponse(
            status="already",
            message="Вы уже отмечены на этом занятии",
            lesson=lesson_brief(lesson),
            streak=await get_attendance_streak(db, user_id, now),
        )
    await db.refresh(attendance)

    reward = await _grant_lesson_rewards(lesson, user_id)
    if reward is not None:
        attendance.rewards_granted_at = now
        await db.commit()

    streak = await get_attendance_streak(db, user_id, now)
    progress = public_progress(await group_progress(db, lesson, only_user_id=user_id))
    character = (reward or {}).get("character")
    unlocked = (reward or {}).get("unlocked_sets") or []

    response = CheckInResponse(
        status="checked_in",
        message="Посещение отмечено! Награды начислены." if reward is not None
        else "Посещение отмечено. Награды будут начислены чуть позже.",
        lesson=lesson_brief(lesson),
        attendance_id=attendance.id,
        verification_method=method.value,
        rewards={
            "coins": lesson.reward_coins,
            "intelligence_points": lesson.reward_intelligence_points,
            "satisfaction": lesson.reward_satisfaction,
        },
        rewards_status="granted" if reward is not None else "pending",
        character=character,
        streak=streak,
        unlocked_sets=unlocked,
        achievements_earned=(reward or {}).get("achievements_earned") or [],
        group_goal=progress[0] if progress else None,
    )

    if background is not None:
        background.add_task(process_group_goals_background, lesson.id, user_id)
        payload = {
            "lesson_id": lesson.id,
            "lesson_name": lesson.name,
            "rewards": response.rewards,
            "rewards_status": response.rewards_status,
            "character": character,
            "streak": {"current": streak.get("current"), "best": streak.get("best")},
            "unlocked_sets": unlocked,
        }
        background.add_task(_attendance_side_effects, user_id, payload)
    return response


# ---------- Эндпоинты для преподавателя / администратора ----------

def _check_lesson_scope(staff: StaffContext, lesson: Lesson) -> None:
    if staff.group_ids is None:
        return
    if not {g.id for g in lesson.groups} & set(staff.group_ids):
        raise HTTPException(status_code=403, detail="Это занятие не относится к вашим группам")


@router.get("/lessons/{lesson_id}/qr", response_model=LessonQRResponse)
async def get_lesson_qr(lesson_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """
    Текущий код занятия и QR-диплинк на мини-приложение (обновляется каждые LESSON_CODE_WINDOW_SECONDS).
    Доступно администратору (токен) и куратору группы занятия (из мини-приложения MAX).
    """
    lesson = await _load_lesson(db, lesson_id)
    _check_lesson_scope(staff, lesson)
    secret = await ensure_lesson_secret(db, lesson)
    now = _utcnow()
    code = codes.current_lesson_code(secret, lesson.id, now)
    payload = codes.build_checkin_payload(lesson.id, code)
    links = codes.build_deep_links(bot_username(), payload)
    return LessonQRResponse(
        lesson_id=lesson.id,
        code=code,
        qr_token=code,
        expires_in_seconds=codes.seconds_until_rotation(now),
        window_seconds=codes.window_seconds(),
        payload=payload,
        deep_link=links["startapp_url"],
        bot_link=links["start_url"],
        qr_code_data=links["startapp_url"] or payload,
    )


@router.get("/lessons/{lesson_id}/qr-image")
async def get_lesson_qr_image(lesson_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """QR-код (PNG) с диплинком на мини-приложение MAX для текущего окна"""
    import qrcode

    data = await get_lesson_qr(lesson_id, staff, db)
    qr = qrcode.QRCode(version=None, box_size=10, border=3)
    qr.add_data(data.qr_code_data)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return Response(
        content=buffer.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-Expires-In": str(data.expires_in_seconds)},
    )


@router.post("/lessons/{lesson_id}/attendance/manual", response_model=CheckInResponse,
             dependencies=[Depends(require_admin)])
async def manual_attendance(
    lesson_id: int,
    request: ManualAttendanceRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Ручная отметка преподавателем/администратором (без кода)"""
    return await perform_lesson_check_in(
        db, lesson_id=lesson_id, user_id=request.user_id, code=None,
        method=VerificationMethod.MANUAL, background=background, skip_code=True,
    )


# ---------- Эндпоинты для студента ----------

@router.post("/lessons/{lesson_id}/check-in", response_model=CheckInResponse)
async def check_in(
    lesson_id: int,
    request: CheckInRequest,
    background: BackgroundTasks,
    user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Отметиться на занятии кодом (или по QR). Возвращает награды и новое состояние персонажа."""
    method = VerificationMethod.QR_CODE if request.method == "qr" else VerificationMethod.MESSAGE
    return await perform_lesson_check_in(
        db, lesson_id=lesson_id, user_id=user_id, code=request.code, method=method, background=background,
    )


@router.post("/internal/lessons/{lesson_id}/check-in", response_model=CheckInResponse)
async def internal_check_in(
    lesson_id: int,
    request: InternalCheckInRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Отметка через чат-бота (внутренний вызов, закрыт на gateway)"""
    method = VerificationMethod.QR_CODE if request.method == "qr" else VerificationMethod.MESSAGE
    return await perform_lesson_check_in(
        db, lesson_id=lesson_id, user_id=request.user_id, code=request.code, method=method, background=background,
    )


class LegacyAttendanceRequest(BaseModel):
    code: Optional[str] = None


class LegacyAttendanceResponse(BaseModel):
    id: int
    lesson_id: int
    user_id: int
    attended_at: datetime
    verification_method: str


@router.post("/lessons/{lesson_id}/attendance", response_model=LegacyAttendanceResponse, status_code=201)
async def create_lesson_attendance(
    lesson_id: int,
    background: BackgroundTasks,
    request: Optional[LegacyAttendanceRequest] = None,
    qr_token: Optional[str] = None,
    user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Старый эндпоинт отметки (совместимость). Теперь код обязателен."""
    code = (request.code if request else None) or qr_token
    if not code:
        raise HTTPException(status_code=400, detail="Требуется код занятия")
    result = await perform_lesson_check_in(
        db, lesson_id=lesson_id, user_id=user_id, code=code,
        method=VerificationMethod.QR_CODE if qr_token else VerificationMethod.MESSAGE, background=background,
    )
    if result.status == "already":
        raise HTTPException(status_code=400, detail="Посещение уже отмечено")
    attendance = (await db.execute(select(LessonAttendance).where(LessonAttendance.id == result.attendance_id))).scalar_one()
    return LegacyAttendanceResponse(
        id=attendance.id,
        lesson_id=attendance.lesson_id,
        user_id=attendance.user_id,
        attended_at=attendance.attended_at or _utcnow(),
        verification_method=attendance.verification_method.value,
    )


# ---------- Расписание студента («Сегодня») ----------

@router.get("/schedule/users/{user_id}")
async def get_user_schedule(user_id: int, days_ahead: int = 7, db: AsyncSession = Depends(get_db)):
    """
    Занятия групп пользователя: текущее, ближайшее и список на сегодня/ближайшие дни
    с отметкой о посещении. Используется экраном «Сегодня» и командой бота /checkin.
    """
    now = _utcnow()
    group_ids = [row[0] for row in (await db.execute(
        select(GroupMember.group_id).where(GroupMember.user_id == user_id)
    )).all()]
    if not group_ids:
        return {"now": now.isoformat(), "current": None, "next": None, "lessons": [], "has_groups": False}

    local_tz = app_timezone()
    day_start_local = now.astimezone(local_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    range_start = day_start_local.astimezone(now.tzinfo)
    range_end = range_start + timedelta(days=max(1, days_ahead))

    lessons = (await db.execute(
        select(Lesson)
        .join(lesson_groups, lesson_groups.c.lesson_id == Lesson.id)
        .where(and_(
            lesson_groups.c.group_id.in_(group_ids),
            Lesson.end_time >= range_start,
            Lesson.start_time <= range_end,
        ))
        .distinct()
    )).scalars().all()
    lessons = sorted(lessons, key=lambda l: as_utc(l.start_time))

    attended = set((await db.execute(select(LessonAttendance.lesson_id).where(and_(
        LessonAttendance.user_id == user_id,
        LessonAttendance.lesson_id.in_([l.id for l in lessons] or [0]),
    )))).scalars().all())

    items = []
    current = nxt = None
    for lesson in lessons:
        start, end = as_utc(lesson.start_time), as_utc(lesson.end_time)
        item = {
            **lesson_brief(lesson),
            "attended": lesson.id in attended,
            "is_now": start - CHECKIN_MARGIN <= now <= end + CHECKIN_MARGIN,
            "is_past": end + CHECKIN_MARGIN < now,
        }
        if item["is_now"]:
            progress = public_progress(await group_progress(db, lesson, only_user_id=user_id))
            item["group_goal"] = progress[0] if progress else None
        items.append(item)
        if item["is_now"] and current is None:
            current = item
        elif start > now and nxt is None:
            nxt = item
    return {"now": now.isoformat(), "current": current, "next": nxt, "lessons": items, "has_groups": True}


@router.get("/schedule/users/{user_id}/current-lesson")
async def get_current_lesson(user_id: int, db: AsyncSession = Depends(get_db)):
    """Текущее занятие пользователя (для команды бота /checkin <код>)"""
    schedule = await get_user_schedule(user_id, 1, db)
    if not schedule["current"]:
        raise HTTPException(status_code=404, detail="Сейчас у вас нет занятия")
    return schedule["current"]
