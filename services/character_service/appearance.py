"""
Кастомизация персонажа и окружения + ежедневные снимки параметров.

Часть сетов открывается за учебную активность (посещённые занятия, серия посещений,
выполненные задачи, уровень) — это связывает геймификацию с образовательной целью;
часть можно купить за монеты. Поля theme_id / organization_id сетов закладывают
возможность брендировать окружения под конкретный вуз/колледж.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import require_admin, require_verified_user
from services.shared.character_mood import growth_stage, mood_from_satisfaction
from services.shared.database import AsyncSessionLocal, get_db
from services.shared.models.appearance import AppearanceKind, AppearanceSet, UnlockType, UserAppearanceUnlock
from services.shared.models.character import Character, CharacterSnapshot
from services.shared.models.social import GroupMember, StudentGroup
from services.shared.models.task import Task, TaskStatus
from services.shared.models.user import User
from services.shared.realtime import push_parameters_update, push_user_event
from services.shared.streaks import get_attendance_streak
from services.shared.timeutil import utcnow

logger = logging.getLogger(__name__)
router = APIRouter()

# code, kind, name, description, asset_key, unlock_type, unlock_value, price, sort
DEFAULT_CATALOG = [
    ("student_basic", AppearanceKind.CHARACTER, "Первокурсник", "Базовый образ", "character:student_basic",
     UnlockType.NONE, 0, None, 10),
    ("scholar", AppearanceKind.CHARACTER, "Эрудит", "Отдельный образ — за 5 посещённых занятий",
     "character:scholar", UnlockType.LESSONS_ATTENDED, 5, None, 20),
    ("night_owl", AppearanceKind.CHARACTER, "Полуночник", "Худи и наушники", "character:night_owl",
     UnlockType.COINS, 0, 150, 30),
    ("champion", AppearanceKind.CHARACTER, "Чемпион дисциплины", "Серия из 7 посещений подряд",
     "character:champion", UnlockType.ATTENDANCE_STREAK, 7, None, 40),
    ("mentor", AppearanceKind.CHARACTER, "Наставник", "Пиджак и шарф — 5 уровень интеллекта",
     "character:mentor", UnlockType.LEVEL, 5, None, 50),
    ("dorm_room", AppearanceKind.ENVIRONMENT, "Комната в общежитии", "Базовая локация", "environment:dorm_room",
     UnlockType.NONE, 0, None, 10),
    ("library", AppearanceKind.ENVIRONMENT, "Библиотека", "Тёплый свет — за 10 посещённых занятий",
     "environment:library", UnlockType.LESSONS_ATTENDED, 10, None, 20),
    ("campus_park", AppearanceKind.ENVIRONMENT, "Парк кампуса", "Свежий воздух и зелень", "environment:campus_park",
     UnlockType.COINS, 0, 200, 30),
    ("lab", AppearanceKind.ENVIRONMENT, "Лаборатория", "За 10 выполненных задач", "environment:lab",
     UnlockType.TASKS_COMPLETED, 10, None, 40),
    ("auditorium", AppearanceKind.ENVIRONMENT, "Большая аудитория", "Серия из 14 посещений подряд",
     "environment:auditorium", UnlockType.ATTENDANCE_STREAK, 14, None, 50),
]

UNLOCK_LABELS = {
    UnlockType.NONE: "Доступно сразу",
    UnlockType.COINS: "Покупка за монеты",
    UnlockType.LESSONS_ATTENDED: "Посещённых занятий",
    UnlockType.ATTENDANCE_STREAK: "Серия посещений",
    UnlockType.TASKS_COMPLETED: "Выполненных задач",
    UnlockType.LEVEL: "Уровень интеллекта",
}


class SetRequest(BaseModel):
    set_id: int


class AppearanceSetCreate(BaseModel):
    kind: str
    code: str
    name: str
    description: Optional[str] = None
    asset_key: str
    unlock_type: str = UnlockType.NONE
    unlock_value: int = 0
    price_coins: Optional[int] = None
    theme_id: Optional[str] = None
    organization_id: Optional[int] = None
    sort_order: int = 100


# ---------- Сиды и метрики ----------

async def seed_appearance_catalog(session: AsyncSession) -> None:
    existing = set((await session.execute(select(AppearanceSet.code))).scalars().all())
    for code, kind, name, description, asset_key, unlock_type, unlock_value, price, sort in DEFAULT_CATALOG:
        if code in existing:
            continue
        session.add(AppearanceSet(
            code=code, kind=kind, name=name, description=description, asset_key=asset_key,
            unlock_type=unlock_type, unlock_value=unlock_value, price_coins=price, sort_order=sort,
            theme_id="default",
        ))
    await session.commit()


async def user_metrics(db: AsyncSession, user_id: int) -> Dict[str, int]:
    streak = await get_attendance_streak(db, user_id)
    tasks_completed = (await db.execute(select(func.count(Task.id)).where(and_(
        Task.user_id == user_id, Task.status == TaskStatus.COMPLETED
    )))).scalar() or 0
    level = (await db.execute(select(Character.intelligence_level).where(Character.user_id == user_id))).scalar() or 1
    coins = (await db.execute(select(User.coins).where(User.id == user_id))).scalar() or 0
    return {
        UnlockType.LESSONS_ATTENDED: streak["lessons_attended"],
        UnlockType.ATTENDANCE_STREAK: streak["best"],
        UnlockType.TASKS_COMPLETED: int(tasks_completed),
        UnlockType.LEVEL: int(level),
        UnlockType.COINS: int(coins),
    }


def set_brief(item: Optional[AppearanceSet]) -> Optional[Dict[str, Any]]:
    if item is None:
        return None
    return {"id": item.id, "code": item.code, "kind": item.kind, "name": item.name, "asset_key": item.asset_key,
            "theme_id": item.theme_id}


async def user_organization_ids(db: AsyncSession, user_id: Optional[int]) -> set:
    """Организации пользователя (через его учебные группы) — для брендированных сетов"""
    if user_id is None:
        return set()
    rows = await db.execute(
        select(StudentGroup.organization_id).join(GroupMember, GroupMember.group_id == StudentGroup.id)
        .where(and_(GroupMember.user_id == user_id, StudentGroup.organization_id.isnot(None)))
    )
    return set(rows.scalars().all())


def visible_to(item: AppearanceSet, org_ids: set) -> bool:
    return item.organization_id is None or item.organization_id in org_ids


async def _unlocked_ids(db: AsyncSession, user_id: int) -> set:
    return set((await db.execute(
        select(UserAppearanceUnlock.set_id).where(UserAppearanceUnlock.user_id == user_id)
    )).scalars().all())


async def character_extras(db: AsyncSession, character: Character) -> Dict[str, Any]:
    """Дополнительные поля ответа персонажа: настроение, стадия роста, активные сеты"""
    mood, mood_label = mood_from_satisfaction(character.satisfaction)
    stage, stage_label = growth_stage(character.intelligence_level)
    ids = [i for i in (character.active_character_set_id, character.active_environment_set_id) if i]
    sets = {}
    if ids:
        sets = {s.id: s for s in (await db.execute(select(AppearanceSet).where(AppearanceSet.id.in_(ids)))).scalars()}
    return {
        "mood": mood,
        "mood_label": mood_label,
        "growth_stage": stage,
        "growth_stage_label": stage_label,
        "active_character_set_id": character.active_character_set_id,
        "active_environment_set_id": character.active_environment_set_id,
        "active_character_set": set_brief(sets.get(character.active_character_set_id)),
        "active_environment_set": set_brief(sets.get(character.active_environment_set_id)),
    }


async def check_unlocks(db: AsyncSession, user_id: int) -> List[Dict[str, Any]]:
    """Автоматически открыть сеты, условия которых выполнены (кроме покупаемых)"""
    metrics = await user_metrics(db, user_id)
    unlocked = await _unlocked_ids(db, user_id)
    candidates = (await db.execute(select(AppearanceSet).where(and_(
        AppearanceSet.is_active.is_(True),
        AppearanceSet.unlock_type.notin_([UnlockType.NONE, UnlockType.COINS]),
    )))).scalars().all()
    newly = []
    for item in candidates:
        if item.id in unlocked:
            continue
        if metrics.get(item.unlock_type, 0) >= (item.unlock_value or 0):
            db.add(UserAppearanceUnlock(user_id=user_id, set_id=item.id, source="auto"))
            try:
                await db.commit()
            except IntegrityError:
                await db.rollback()
                continue
            newly.append(set_brief(item))
    if newly:
        await push_user_event(user_id, "appearance.unlocked", payload={"sets": newly})
    return newly


# ---------- Эндпоинты ----------

@router.get("/characters/appearance/catalog")
async def get_catalog(user_id: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """Каталог сетов со статусом разблокировки и прогрессом для пользователя"""
    sets = (await db.execute(
        select(AppearanceSet).where(AppearanceSet.is_active.is_(True)).order_by(AppearanceSet.kind, AppearanceSet.sort_order)
    )).scalars().all()
    metrics: Dict[str, int] = {}
    unlocked: set = set()
    character = None
    if user_id is not None:
        # Досчитываем разблокировки: условия могли выполниться без начисления награды
        # (история посещений, импорт, ручная отметка куратора)
        await check_unlocks(db, user_id)
        metrics = await user_metrics(db, user_id)
        unlocked = await _unlocked_ids(db, user_id)
        character = (await db.execute(select(Character).where(Character.user_id == user_id))).scalar_one_or_none()
    equipped = {getattr(character, "active_character_set_id", None), getattr(character, "active_environment_set_id", None)}

    org_ids = await user_organization_ids(db, user_id)
    items = []
    for item in sets:
        if not visible_to(item, org_ids):
            continue
        is_unlocked = item.unlock_type == UnlockType.NONE or item.id in unlocked
        required = item.price_coins if item.unlock_type == UnlockType.COINS else item.unlock_value
        items.append({
            **set_brief(item),
            "description": item.description,
            "unlock_type": item.unlock_type,
            "unlock_label": UNLOCK_LABELS.get(item.unlock_type, item.unlock_type),
            "unlock_value": item.unlock_value,
            "price_coins": item.price_coins,
            "organization_id": item.organization_id,
            "unlocked": is_unlocked,
            "equipped": item.id in equipped,
            "progress": {"current": metrics.get(item.unlock_type, 0), "required": required or 0},
        })
    return {
        "characters": [i for i in items if i["kind"] == AppearanceKind.CHARACTER],
        "environments": [i for i in items if i["kind"] == AppearanceKind.ENVIRONMENT],
    }


async def _get_set(db: AsyncSession, set_id: int) -> AppearanceSet:
    item = (await db.execute(select(AppearanceSet).where(AppearanceSet.id == set_id))).scalar_one_or_none()
    if item is None or not item.is_active:
        raise HTTPException(status_code=404, detail="Сет не найден")
    return item


@router.post("/characters/user/{user_id}/appearance/equip")
async def equip_set(
    user_id: int,
    request: SetRequest,
    acting_user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Надеть открытый сет внешности или выбрать открытое окружение"""
    if acting_user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя менять чужого персонажа")
    item = await _get_set(db, request.set_id)
    if not visible_to(item, await user_organization_ids(db, user_id)):
        raise HTTPException(status_code=403, detail="Этот сет доступен только студентам другой организации")
    if item.unlock_type != UnlockType.NONE and item.id not in await _unlocked_ids(db, user_id):
        await check_unlocks(db, user_id)
        if item.id not in await _unlocked_ids(db, user_id):
            raise HTTPException(status_code=400, detail="Этот сет ещё не открыт")
    character = (await db.execute(select(Character).where(Character.user_id == user_id))).scalar_one_or_none()
    if character is None:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    if item.kind == AppearanceKind.CHARACTER:
        character.active_character_set_id = item.id
    else:
        character.active_environment_set_id = item.id
    await db.commit()
    await db.refresh(character)
    extras = await character_extras(db, character)
    await push_user_event(user_id, "appearance.changed", payload=extras)
    return {"success": True, **extras}


@router.post("/characters/user/{user_id}/appearance/purchase")
async def purchase_set(
    user_id: int,
    request: SetRequest,
    acting_user_id: int = Depends(require_verified_user),
    db: AsyncSession = Depends(get_db),
):
    """Купить сет за монеты (атомарное списание)"""
    if acting_user_id != user_id:
        raise HTTPException(status_code=403, detail="Нельзя покупать за другого пользователя")
    item = await _get_set(db, request.set_id)
    if item.unlock_type != UnlockType.COINS or not item.price_coins:
        raise HTTPException(status_code=400, detail="Этот сет не продаётся — он открывается за учебную активность")
    if item.id in await _unlocked_ids(db, user_id):
        raise HTTPException(status_code=400, detail="Сет уже куплен")
    result = await db.execute(
        update(User).where(and_(User.id == user_id, User.coins >= item.price_coins))
        .values(coins=User.coins - item.price_coins)
    )
    if not result.rowcount:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Недостаточно монет")
    db.add(UserAppearanceUnlock(user_id=user_id, set_id=item.id, source="purchase"))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Сет уже куплен")
    coins = (await db.execute(select(User.coins).where(User.id == user_id))).scalar()
    await push_parameters_update(user_id, coins=coins, source="character_service.purchase_set")
    return {"success": True, "set": set_brief(item), "coins": coins}


@router.post("/characters/user/{user_id}/appearance/check-unlocks")
async def check_unlocks_endpoint(user_id: int, db: AsyncSession = Depends(get_db)):
    """Внутренний вызов Reward Service после начисления (закрыт на gateway)"""
    return {"unlocked": await check_unlocks(db, user_id)}


@router.post("/characters/appearance/sets", dependencies=[Depends(require_admin)], status_code=201)
async def create_set(request: AppearanceSetCreate, db: AsyncSession = Depends(get_db)):
    """Добавить сет (например, брендированное окружение вуза)"""
    if request.kind not in (AppearanceKind.CHARACTER, AppearanceKind.ENVIRONMENT):
        raise HTTPException(status_code=400, detail="kind должен быть character или environment")
    item = AppearanceSet(**request.model_dump())
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Сет с таким code уже существует")
    await db.refresh(item)
    return set_brief(item)


# ---------- Снимки для дашборда куратора ----------

async def write_daily_snapshots(session: AsyncSession, today: Optional[date] = None) -> int:
    """Один снимок в сутки на пользователя (повторный вызов в тот же день обновляет значения)"""
    today = today or utcnow().date()
    rows = (await session.execute(select(Character, User.coins).join(User, User.id == Character.user_id))).all()
    existing = {s.user_id: s for s in (await session.execute(
        select(CharacterSnapshot).where(CharacterSnapshot.snapshot_date == today)
    )).scalars()}
    for character, coins in rows:
        snap = existing.get(character.user_id)
        if snap is None:
            session.add(CharacterSnapshot(
                user_id=character.user_id, snapshot_date=today,
                satisfaction=character.satisfaction, intelligence_level=character.intelligence_level,
                intelligence_points=character.intelligence_points, coins=coins or 0,
            ))
        else:
            snap.satisfaction = character.satisfaction
            snap.intelligence_level = character.intelligence_level
            snap.intelligence_points = character.intelligence_points
            snap.coins = coins or 0
    await session.commit()
    return len(rows)


async def snapshot_worker(interval_seconds: int = 3600) -> None:
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await write_daily_snapshots(session)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("Снимок параметров не записан: %s", exc)
        await asyncio.sleep(interval_seconds)


async def seed_on_startup() -> None:
    try:
        async with AsyncSessionLocal() as session:
            await seed_appearance_catalog(session)
    except Exception as exc:
        logger.warning("Каталог кастомизации не создан: %s", exc)
