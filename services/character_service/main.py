"""
Character Service - Управление персонажами
Порт: 8002
"""
import asyncio
import logging

from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

from services.shared.database import AsyncSessionLocal, get_db, init_db, execute_migration_sql
from services.shared.realtime import push_parameters_update
from services.shared.models.character import Character
from services.shared.models.user import User
from services.shared.utils import ServiceClient
# Импортируем TaskGeneration для корректной инициализации relationship в User
from services.shared.models.task_generation import TaskGeneration
from services.shared.migrations import apply_hackathon_migrations
from services.character_service import appearance

# Pydantic схемы
class CharacterCreate(BaseModel):
    user_id: int
    name: str
    satisfaction: int = 50
    intelligence_level: int = 1
    intelligence_points: int = 0
    bonus_points: int = 0

class CharacterUpdate(BaseModel):
    name: str | None = None
    satisfaction: int | None = None
    intelligence_level: int | None = None
    intelligence_points: int | None = None
    bonus_points: int | None = None

class CharacterResponse(BaseModel):
    id: int
    user_id: int
    name: str
    satisfaction: int
    intelligence_level: int
    intelligence_points: int
    bonus_points: int
    rating: float
    # Кастомизация и визуальное состояние
    active_character_set_id: Optional[int] = None
    active_environment_set_id: Optional[int] = None
    active_character_set: Optional[Dict[str, Any]] = None
    active_environment_set: Optional[Dict[str, Any]] = None
    mood: Optional[str] = None
    mood_label: Optional[str] = None
    growth_stage: Optional[str] = None
    growth_stage_label: Optional[str] = None

    class Config:
        from_attributes = True


async def character_payload(db: AsyncSession, character: Character) -> CharacterResponse:
    base = CharacterResponse.model_validate(character).model_dump()
    base.update(await appearance.character_extras(db, character))
    return CharacterResponse(**base)

# FastAPI приложение
app = FastAPI(title="Character Service", version="1.0.0")

logger = logging.getLogger(__name__)

SATISFACTION_DECAY_POINTS = 20
SATISFACTION_DECAY_PERIOD = timedelta(days=1)
DECAY_CHECK_INTERVAL_SECONDS = 60 * 60 * 2  # Проверяем каждый час
SATISFACTION_THRESHOLD = 30  # Порог для отправки уведомления (30%)
_decay_task: asyncio.Task | None = None
_snapshot_task: asyncio.Task | None = None


async def apply_character_migrations():
    migration_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='characters' AND column_name='last_satisfaction_decay'
        ) THEN
            ALTER TABLE characters ADD COLUMN last_satisfaction_decay TIMESTAMPTZ;
        END IF;
    END $$;
    """
    await execute_migration_sql(migration_sql)


async def satisfaction_decay_worker():
    """
    Периодически уменьшает удовлетворение всех персонажей на фиксированное значение.
    """
    while True:
        try:
            now = datetime.now(timezone.utc)
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Character).where(Character.satisfaction > 0)
                )
                characters = result.scalars().all()
                if not characters:
                    # Закрываем транзакцию до сна: иначе сессия часами держит блокировку таблицы
                    await session.rollback()
                    await asyncio.sleep(DECAY_CHECK_INTERVAL_SECONDS)
                    continue

                updates: list[tuple[int, int, float]] = []
                low_satisfaction_notifications: list[tuple[int, int, str]] = []
                
                for character in characters:
                    last_decay = character.last_satisfaction_decay or character.created_at or now
                    if (now - last_decay) < SATISFACTION_DECAY_PERIOD:
                        continue
                    before = character.satisfaction
                    character.adjust_satisfaction(-SATISFACTION_DECAY_POINTS)
                    character.last_satisfaction_decay = now
                    if character.satisfaction != before:
                        updates.append(
                            (character.user_id, character.satisfaction, character.rating)
                        )
                        # Проверяем переход через порог 30%
                        if before > SATISFACTION_THRESHOLD and character.satisfaction <= SATISFACTION_THRESHOLD:
                            low_satisfaction_notifications.append(
                                (character.user_id, character.satisfaction, character.name)
                            )

                if updates:
                    await session.commit()
                else:
                    await session.rollback()

                for user_id, satisfaction, rating in updates:
                    await push_parameters_update(
                        user_id,
                        satisfaction=satisfaction,
                        rating=rating,
                        source="character_service.satisfaction_decay",
                    )
                
                # Отправляем уведомления о низкой удовлетворённости
                for user_id, satisfaction, character_name in low_satisfaction_notifications:
                    try:
                        bot_service = ServiceClient("max_bot")
                        await bot_service.post("/notifications/low-satisfaction", json={
                            "user_id": user_id,
                            "satisfaction": satisfaction,
                            "character_name": character_name
                        })
                        await bot_service.close()
                        logger.info(f"Отправлено уведомление о низкой удовлетворённости пользователю {user_id} (satisfaction={satisfaction}%)")
                    except Exception as e:
                        logger.warning(f"Не удалось отправить уведомление о низкой удовлетворённости пользователю {user_id}: {e}")

                logger.info(
                    "Снижение удовлетворения выполнено. Обновлено записей: %s",
                    len(updates),
                )
        except asyncio.CancelledError:
            logger.info("Остановка фоновой задачи снижения удовлетворения")
            raise
        except Exception as exc:
            logger.exception(
                "Ошибка при снижении удовлетворения персонажей: %s", exc
            )

        await asyncio.sleep(DECAY_CHECK_INTERVAL_SECONDS)


@app.on_event("startup")
async def startup():
    await init_db()
    await apply_character_migrations()
    await apply_hackathon_migrations()
    await appearance.seed_on_startup()
    global _decay_task, _snapshot_task
    if _decay_task is None or _decay_task.done():
        _decay_task = asyncio.create_task(satisfaction_decay_worker())
    if _snapshot_task is None or _snapshot_task.done():
        _snapshot_task = asyncio.create_task(appearance.snapshot_worker())


@app.on_event("shutdown")
async def shutdown():
    global _decay_task
    if _decay_task is not None:
        _decay_task.cancel()
        try:
            await _decay_task
        except asyncio.CancelledError:
            pass
        _decay_task = None
    if _snapshot_task is not None:
        _snapshot_task.cancel()

# Кастомизация персонажа и окружения
app.include_router(appearance.router)

@app.get("/")
async def root():
    return {"service": "Character Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD эндпоинты
@app.post("/characters/", response_model=CharacterResponse, status_code=201)
async def create_character(char_in: CharacterCreate, db: AsyncSession = Depends(get_db)):
    """Создать персонажа"""
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == char_in.user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверка, что у пользователя нет персонажа
    result = await db.execute(select(Character).where(Character.user_id == char_in.user_id))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="У пользователя уже есть персонаж")
    
    character_data = char_in.model_dump()
    character = Character(**character_data)
    character.last_satisfaction_decay = datetime.now(timezone.utc)
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character

@app.get("/characters/", response_model=List[CharacterResponse])
async def list_characters(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Список персонажей"""
    result = await db.execute(select(Character).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/characters/{character_id}", response_model=CharacterResponse)
async def get_character(character_id: int, db: AsyncSession = Depends(get_db)):
    """Получить персонажа по ID"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    return await character_payload(db, character)

@app.get("/characters/user/{user_id}", response_model=CharacterResponse)
async def get_character_by_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получить персонажа пользователя"""
    result = await db.execute(select(Character).where(Character.user_id == user_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    return await character_payload(db, character)

# Бизнес-логика
@app.post("/characters/{character_id}/satisfaction/adjust")
async def adjust_satisfaction(character_id: int, amount: int, db: AsyncSession = Depends(get_db)):
    """Изменить удовлетворение персонажа"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    
    before = character.satisfaction
    character.adjust_satisfaction(amount)
    await db.commit()
    await db.refresh(character)

    await push_parameters_update(
        character.user_id,
        satisfaction=character.satisfaction,
        rating=character.rating,
        source="character_service.adjust_satisfaction",
        metadata={"amount": amount},
    )
    
    # Проверяем переход через порог 30% (только при уменьшении)
    if amount < 0 and before > SATISFACTION_THRESHOLD and character.satisfaction <= SATISFACTION_THRESHOLD:
        try:
            bot_service = ServiceClient("max_bot")
            await bot_service.post("/notifications/low-satisfaction", json={
                "user_id": character.user_id,
                "satisfaction": character.satisfaction,
                "character_name": character.name
            })
            await bot_service.close()
            logger.info(f"Отправлено уведомление о низкой удовлетворённости пользователю {character.user_id} (satisfaction={character.satisfaction}%)")
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о низкой удовлетворённости пользователю {character.user_id}: {e}")
    
    return {"character_id": character.id, "satisfaction": character.satisfaction, "rating": character.rating}

class IntelligenceAddRequest(BaseModel):
    points: int

@app.post("/characters/{character_id}/intelligence/add")
async def add_intelligence_points(character_id: int, request: IntelligenceAddRequest, db: AsyncSession = Depends(get_db)):
    """Добавить очки интеллекта (с автоматическим повышением уровня)"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    
    old_level = character.intelligence_level
    character.add_intelligence_points(request.points)
    await db.commit()
    await db.refresh(character)
    
    level_up = character.intelligence_level > old_level

    await push_parameters_update(
        character.user_id,
        intelligence_level=character.intelligence_level,
        intelligence_points=character.intelligence_points,
        rating=character.rating,
        source="character_service.add_intelligence_points",
        metadata={
            "points_added": request.points,
            "level_up": level_up,
            "levels_gained": character.intelligence_level - old_level,
        },
    )
    return {
        "character_id": character.id,
        "intelligence_level": character.intelligence_level,
        "intelligence_points": character.intelligence_points,
        "rating": character.rating,
        "level_up": level_up,
        "levels_gained": character.intelligence_level - old_level
    }

@app.post("/characters/{character_id}/bonus/add")
async def add_bonus_points(character_id: int, points: int, db: AsyncSession = Depends(get_db)):
    """Добавить бонусные очки рейтинга"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    
    character.bonus_points += points
    await db.commit()
    await db.refresh(character)

    await push_parameters_update(
        character.user_id,
        rating=character.rating,
        source="character_service.add_bonus_points",
        metadata={"bonus_points": character.bonus_points},
    )
    return {"character_id": character.id, "bonus_points": character.bonus_points, "rating": character.rating}

@app.get("/characters/{character_id}/rating")
async def get_rating(character_id: int, db: AsyncSession = Depends(get_db)):
    """Получить рейтинг персонажа"""
    result = await db.execute(select(Character).where(Character.id == character_id))
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж не найден")
    
    return {
        "character_id": character.id,
        "rating": character.rating,
        "satisfaction": character.satisfaction,
        "intelligence_level": character.intelligence_level,
        "bonus_points": character.bonus_points
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

