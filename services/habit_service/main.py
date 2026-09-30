"""
Habit Service - Управление привычками
Порт: 8004
"""
import asyncio
import logging
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func as sql_func
import sqlalchemy
from typing import List, Optional, Dict, Tuple
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel, Field

from services.shared.database import get_db, init_db, AsyncSessionLocal
from services.shared.models.habit import Habit, HabitLog, HabitFrequency
from services.shared.models.user import User
from services.shared.utils import ServiceClient
from services.habit_service.habit_evaluator import HabitEvaluator

# Pydantic схемы
class HabitCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    frequency: HabitFrequency = HabitFrequency.DAILY
    target_count: int = Field(default=1, ge=1)

class HabitUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    frequency: Optional[HabitFrequency] = None
    target_count: Optional[int] = Field(None, ge=1)

class HabitResponse(BaseModel):
    id: int
    user_id: int
    name: str
    description: Optional[str]
    frequency: HabitFrequency
    target_count: int
    created_at: datetime
    updated_at: Optional[datetime]
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int
    
    class Config:
        from_attributes = True

class HabitLogCreate(BaseModel):
    notes: Optional[str] = None

class HabitLogResponse(BaseModel):
    id: int
    habit_id: int
    completed_at: datetime
    notes: Optional[str]
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int
    
    class Config:
        from_attributes = True

# FastAPI приложение
app = FastAPI(title="Habit Service", version="1.0.0")
habit_evaluator = HabitEvaluator()
logger = logging.getLogger(__name__)

# Фоновая задача для проверки активации привычек
HABIT_CHECK_INTERVAL_SECONDS = 60 * 60  # Проверка каждый час
_notification_check_task: asyncio.Task | None = None
_sent_notifications: Dict[Tuple[int, str], datetime] = {}  # (habit_id, period_start_str) -> last_sent

_HABIT_REWARD_LIMITS = {
    HabitFrequency.DAILY.value: {
        "min_coins": 2,
        "max_coins": 8,
        "min_intelligence": 1,
        "max_intelligence": 4,
        "min_satisfaction": 2,
        "max_satisfaction": 6,
    },
    HabitFrequency.WEEKLY.value: {
        "min_coins": 3,
        "max_coins": 10,
        "min_intelligence": 1,
        "max_intelligence": 5,
        "min_satisfaction": 3,
        "max_satisfaction": 7,
    },
    HabitFrequency.MONTHLY.value: {
        "min_coins": 4,
        "max_coins": 12,
        "min_intelligence": 1,
        "max_intelligence": 5,
        "min_satisfaction": 4,
        "max_satisfaction": 8,
    },
}


def _normalize_habit_rewards(
    coins: int,
    intelligence: int,
    satisfaction: int,
    frequency: str,
    target_count: int
) -> tuple[int, int, int]:
    freq_value = frequency
    if isinstance(freq_value, HabitFrequency):
        freq_value = freq_value.value
    freq_key = str(freq_value or HabitFrequency.DAILY.value).lower()
    limits = _HABIT_REWARD_LIMITS.get(freq_key, _HABIT_REWARD_LIMITS[HabitFrequency.DAILY.value])

    coins = int(round(coins or 0))
    intelligence = int(round(intelligence or 0))
    satisfaction = int(round(satisfaction or 0))

    if target_count and target_count > 1:
        coins += min(target_count - 1, 2)

    coins = max(limits["min_coins"], min(limits["max_coins"], coins))
    if coins <= 0:
        return 0, 0, 0

    intelligence = max(limits["min_intelligence"], min(limits["max_intelligence"], intelligence))
    satisfaction = max(limits["min_satisfaction"], min(limits["max_satisfaction"], satisfaction))

    return coins, intelligence, satisfaction


def _get_period_bounds(
    frequency: HabitFrequency | str,
    reference: datetime | None = None
) -> tuple[datetime, datetime]:
    if reference is None:
        reference = datetime.now(timezone.utc)
    ref = reference.astimezone(timezone.utc)
    start = ref.replace(hour=0, minute=0, second=0, microsecond=0)

    freq_value = frequency.value if isinstance(frequency, HabitFrequency) else str(frequency or HabitFrequency.DAILY.value)
    freq_value = freq_value.lower()

    if freq_value == HabitFrequency.WEEKLY.value:
        # ISO week: Monday = 0
        weekday = start.weekday()
        start -= timedelta(days=weekday)
        end = start + timedelta(days=7)
    elif freq_value == HabitFrequency.MONTHLY.value:
        start = start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
    else:
        end = start + timedelta(days=1)
    return start, end


async def _get_current_period_log(
    db: AsyncSession,
    habit_id: int,
    frequency: HabitFrequency | str
) -> Optional[HabitLog]:
    period_start, period_end = _get_period_bounds(frequency)
    result = await db.execute(
        select(HabitLog)
        .where(
            HabitLog.habit_id == habit_id,
            HabitLog.completed_at >= period_start,
            HabitLog.completed_at < period_end
        )
        .order_by(HabitLog.completed_at.desc())
    )
    return result.scalars().first()


async def _check_and_notify_activated_habits():
    """
    Проверяет все привычки и отправляет уведомления для активированных (начался новый период)
    """
    # Первая проверка произойдет сразу после запуска
    while True:
        try:
            try:
                async with AsyncSessionLocal() as session:
                    # Получаем все привычки
                    result = await session.execute(select(Habit))
                    habits = result.scalars().all()
                    
                    if not habits:
                        # Закрываем транзакцию до сна: иначе сессия часами держит блокировку таблицы
                        await session.rollback()
                        await asyncio.sleep(HABIT_CHECK_INTERVAL_SECONDS)
                        continue
                    
                    current_time = datetime.now(timezone.utc)
                    notifications_to_send = []
                    
                    for habit in habits:
                        try:
                            # Получаем границы текущего периода
                            period_start, period_end = _get_period_bounds(habit.frequency, current_time)
                            period_start_str = period_start.isoformat()
                            
                            # Проверяем, не отправляли ли уже уведомление для этого периода
                            notification_key = (habit.id, period_start_str)
                            if notification_key in _sent_notifications:
                                continue
                            
                            # Проверяем, есть ли выполнение в текущем периоде
                            existing_log = await _get_current_period_log(session, habit.id, habit.frequency)
                            
                            # Если нет выполнения, значит привычка активирована
                            if not existing_log:
                                notifications_to_send.append((habit, period_start_str))
                                _sent_notifications[notification_key] = current_time
                                
                        except Exception as e:
                            logger.warning(f"Ошибка при проверке привычки {habit.id}: {e}")
                            continue
                    
                    # Отправляем уведомления (вне сессии, чтобы не зависеть от неё)
                    bot_service = ServiceClient("max_bot")
                    try:
                        for habit, period_start_str in notifications_to_send:
                            try:
                                await bot_service.post("/notifications/habit-activated", json={
                                    "user_id": habit.user_id,
                                    "habit_name": habit.name,
                                    "frequency": habit.frequency.value if isinstance(habit.frequency, HabitFrequency) else str(habit.frequency)
                                })
                                logger.info(f"Отправлено уведомление об активации привычки {habit.id} ({habit.name}) пользователю {habit.user_id}")
                            except Exception as e:
                                logger.warning(f"Не удалось отправить уведомление об активации привычки {habit.id}: {e}")
                    finally:
                        await bot_service.close()
                    
                    # Очищаем старые записи из словаря (старше 7 дней)
                    cutoff_time = current_time - timedelta(days=7)
                    keys_to_remove = [
                        key for key, sent_time in _sent_notifications.items()
                        if sent_time < cutoff_time
                    ]
                    for key in keys_to_remove:
                        del _sent_notifications[key]
                    
                    if notifications_to_send:
                        logger.info(f"Проверка активации привычек завершена. Отправлено уведомлений: {len(notifications_to_send)}")
                    
                    # Ждём перед следующей проверкой (транзакция закрыта, блокировки сняты)
                    await session.commit()
                    await asyncio.sleep(HABIT_CHECK_INTERVAL_SECONDS)
            except (sqlalchemy.exc.DBAPIError, ConnectionError, OSError) as session_exc:
                # Если ошибка соединения произошла внутри сессии, пробрасываем её наверх
                raise
                    
        except asyncio.CancelledError:
            logger.info("Остановка фоновой задачи проверки активации привычек")
            raise
        except (sqlalchemy.exc.DBAPIError, ConnectionError, OSError) as exc:
            # Обрабатываем ошибки соединения - соединение могло быть закрыто
            error_msg = str(exc)
            if "connection was closed" in error_msg.lower() or "connection does not exist" in error_msg.lower():
                logger.warning(f"Соединение с БД было закрыто, переподключаемся: {exc}")
            else:
                logger.exception(f"Ошибка соединения с БД при проверке активации привычек: {exc}")
            # Ждём перед повтором при ошибке соединения
            await asyncio.sleep(60)
        except Exception as exc:
            logger.exception(f"Ошибка при проверке активации привычек: {exc}")
            await asyncio.sleep(60)  # Ждём минуту перед повтором при ошибке

@app.on_event("startup")
async def startup():
    await init_db()
    global _notification_check_task
    if _notification_check_task is None or _notification_check_task.done():
        _notification_check_task = asyncio.create_task(_check_and_notify_activated_habits())
        logger.info("Фоновая задача проверки активации привычек запущена")


@app.on_event("shutdown")
async def shutdown():
    global _notification_check_task
    if _notification_check_task is not None:
        _notification_check_task.cancel()
        try:
            await _notification_check_task
        except asyncio.CancelledError:
            pass
        _notification_check_task = None
        logger.info("Фоновая задача проверки активации привычек остановлена")

@app.get("/")
async def root():
    return {"service": "Habit Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD привычек
@app.post("/habits/", response_model=HabitResponse, status_code=201)
async def create_habit(
    habit_in: HabitCreate,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """Создать привычку для пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверка полезности привычки
    is_harmful = await habit_evaluator.is_habit_harmful(
        name=habit_in.name,
        description=habit_in.description
    )
    if is_harmful:
        raise HTTPException(status_code=400, detail="Привычка не является полезной")

    reward_coins, reward_intelligence_points, reward_satisfaction = await habit_evaluator.evaluate_rewards(
        name=habit_in.name,
        description=habit_in.description,
        frequency=habit_in.frequency.value,
        target_count=habit_in.target_count
    )
    reward_coins, reward_intelligence_points, reward_satisfaction = _normalize_habit_rewards(
        reward_coins,
        reward_intelligence_points,
        reward_satisfaction,
        habit_in.frequency.value,
        habit_in.target_count
    )

    habit_data = habit_in.model_dump()
    habit_data["reward_coins"] = reward_coins
    habit_data["reward_intelligence_points"] = reward_intelligence_points
    habit_data["reward_satisfaction"] = reward_satisfaction
    habit = Habit(**habit_data, user_id=user_id)
    db.add(habit)
    await db.commit()
    await db.refresh(habit)
    return habit

@app.get("/habits/", response_model=List[HabitResponse])
async def list_habits(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Список всех привычек"""
    result = await db.execute(select(Habit).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/habits/{habit_id}", response_model=HabitResponse)
async def get_habit(habit_id: int, db: AsyncSession = Depends(get_db)):
    """Получить привычку по ID"""
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    return habit

@app.get("/habits/user/{user_id}", response_model=List[HabitResponse])
async def get_user_habits(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить привычки пользователя"""
    result = await db.execute(
        select(Habit).where(Habit.user_id == user_id).offset(skip).limit(limit)
    )
    return result.scalars().all()

@app.put("/habits/{habit_id}", response_model=HabitResponse)
async def update_habit(
    habit_id: int,
    habit_in: HabitUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить привычку"""
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    
    update_data = habit_in.model_dump(exclude_unset=True)

    re_evaluate = any(field in update_data for field in ["name", "description", "frequency", "target_count"])

    for field, value in update_data.items():
        setattr(habit, field, value)

    if re_evaluate:
        is_harmful = await habit_evaluator.is_habit_harmful(
            name=habit.name,
            description=habit.description
        )
        if is_harmful:
            raise HTTPException(status_code=400, detail="Привычка не является полезной")

        reward_coins, reward_intelligence_points, reward_satisfaction = await habit_evaluator.evaluate_rewards(
            name=habit.name,
            description=habit.description,
            frequency=habit.frequency.value if habit.frequency else HabitFrequency.DAILY.value,
            target_count=habit.target_count
        )
        reward_coins, reward_intelligence_points, reward_satisfaction = _normalize_habit_rewards(
            reward_coins,
            reward_intelligence_points,
            reward_satisfaction,
            habit.frequency,
            habit.target_count
        )

        habit.reward_coins = reward_coins
        habit.reward_intelligence_points = reward_intelligence_points
        habit.reward_satisfaction = reward_satisfaction
    
    await db.commit()
    await db.refresh(habit)
    return habit

@app.delete("/habits/{habit_id}", response_model=HabitResponse)
async def delete_habit(habit_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить привычку"""
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    
    await db.delete(habit)
    return habit

# Логирование выполнения
@app.post("/habits/{habit_id}/complete")
async def log_habit_completion(
    habit_id: int,
    log_in: HabitLogCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Залогировать выполнение привычки и выдать награды
    """
    # Получить привычку
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Привычка не найдена")

    existing_log = await _get_current_period_log(db, habit_id, habit.frequency)
    if existing_log:
        raise HTTPException(status_code=400, detail="Привычка уже выполнена в текущем периоде")
    
    # Создать лог
    normalized_coins, normalized_intelligence, normalized_satisfaction = _normalize_habit_rewards(
        habit.reward_coins,
        habit.reward_intelligence_points,
        habit.reward_satisfaction,
        habit.frequency,
        habit.target_count
    )

    log = HabitLog(
        habit_id=habit_id,
        notes=log_in.notes,
        reward_coins=normalized_coins,
        reward_intelligence_points=normalized_intelligence,
        reward_satisfaction=normalized_satisfaction
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    if (
        normalized_coins != habit.reward_coins
        or normalized_intelligence != habit.reward_intelligence_points
        or normalized_satisfaction != habit.reward_satisfaction
    ):
        habit.reward_coins = normalized_coins
        habit.reward_intelligence_points = normalized_intelligence
        habit.reward_satisfaction = normalized_satisfaction
        await db.commit()
        await db.refresh(habit)
    
    # Выдать награды через Reward Service
    reward_service = ServiceClient("reward")
    try:
        rewards = await reward_service.post("/rewards/grant", json={
            "user_id": habit.user_id,
            "coins": normalized_coins,
            "intelligence_points": normalized_intelligence,
            "satisfaction": normalized_satisfaction,
            "source": "habit_completion",
            "source_ref": f"habit:{habit.id}",
        })
        
        # Проверить соревнования после логирования привычки
        competition_service = ServiceClient("competition")
        try:
            await competition_service.get(f"/competitions/check-goal/{habit.user_id}")
        except Exception as e:
            # Игнорируем ошибки проверки соревнований
            logger.debug(f"Проверка соревнований не выполнена: {str(e)}")
        finally:
            await competition_service.close()
        
        return {
            "log": HabitLogResponse.model_validate(log),
            "rewards": rewards
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче наград: {str(e)}")
    finally:
        await reward_service.close()

@app.post("/habits/{habit_id}/skip")
async def skip_habit(
    habit_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отметить, что привычка не выполнена сегодня"""
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Привычка не найдена")

    log = await _get_current_period_log(db, habit_id, habit.frequency)
    if not log:
        return {
            "status": "skipped",
            "habit_id": habit_id,
            "reverted_rewards": {
                "coins": 0,
                "intelligence_points": 0,
                "satisfaction": 0
            }
        }

    reward_service = ServiceClient("reward")
    try:
        if log.reward_coins or log.reward_intelligence_points or log.reward_satisfaction:
            await reward_service.post("/rewards/grant", json={
                "user_id": habit.user_id,
                "coins": -log.reward_coins,
                "intelligence_points": -log.reward_intelligence_points,
                "satisfaction": -log.reward_satisfaction
            })
        await db.delete(log)
        await db.commit()
        return {
            "status": "skipped",
            "habit_id": habit_id,
            "reverted_rewards": {
                "coins": log.reward_coins,
                "intelligence_points": log.reward_intelligence_points,
                "satisfaction": log.reward_satisfaction
            }
        }
    except HTTPException as http_exc:
        await db.rollback()
        if http_exc.status_code == 400:
            return {
                "status": "insufficient_resources",
                "habit_id": habit_id,
                "reverted_rewards": {
                    "coins": log.reward_coins,
                    "intelligence_points": log.reward_intelligence_points,
                    "satisfaction": log.reward_satisfaction
                }
            }
        raise
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Не удалось отменить награды: {exc}")
    finally:
        await reward_service.close()

# Статистика
@app.get("/habits/{habit_id}/streak")
async def get_habit_streak(habit_id: int, db: AsyncSession = Depends(get_db)):
    """Рассчитать серию выполнения привычки"""
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    habit = result.scalar_one_or_none()
    if not habit:
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    
    # Получить все логи привычки
    result = await db.execute(
        select(HabitLog)
        .where(HabitLog.habit_id == habit_id)
        .order_by(HabitLog.completed_at.desc())
    )
    logs = result.scalars().all()
    
    if not logs:
        return {"habit_id": habit_id, "current_streak": 0, "longest_streak": 0}
    
    # Рассчитать текущую серию
    current_streak = 0
    today = datetime.now().date()
    
    for i, log in enumerate(logs):
        log_date = log.completed_at.date()
        if i == 0 and log_date == today:
            current_streak = 1
        elif i > 0:
            prev_log = logs[i-1]
            prev_date = prev_log.completed_at.date()
            if (prev_date - log_date).days == 1:
                current_streak += 1
            else:
                break
    
    # Рассчитать самую длинную серию (упрощенно)
    longest_streak = max(current_streak, len(logs))
    
    return {
        "habit_id": habit_id,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "total_completions": len(logs)
    }

@app.get("/habits/{habit_id}/calendar")
async def get_habit_calendar(
    habit_id: int,
    year: int,
    month: int,
    db: AsyncSession = Depends(get_db)
):
    """Календарь выполнения привычки за месяц"""
    result = await db.execute(select(Habit).where(Habit.id == habit_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Привычка не найдена")
    
    # Получить логи за указанный месяц
    start_date = datetime(year, month, 1)
    if month == 12:
        end_date = datetime(year + 1, 1, 1)
    else:
        end_date = datetime(year, month + 1, 1)
    
    result = await db.execute(
        select(HabitLog)
        .where(and_(
            HabitLog.habit_id == habit_id,
            HabitLog.completed_at >= start_date,
            HabitLog.completed_at < end_date
        ))
        .order_by(HabitLog.completed_at)
    )
    logs = result.scalars().all()
    
    # Сгруппировать по дням
    calendar = {}
    for log in logs:
        day = log.completed_at.day
        if day not in calendar:
            calendar[day] = []
        calendar[day].append({
            "id": log.id,
            "completed_at": log.completed_at.isoformat(),
            "notes": log.notes
        })
    
    return {
        "habit_id": habit_id,
        "year": year,
        "month": month,
        "calendar": calendar,
        "total_days": len(calendar)
    }

@app.get("/habits/stats/{user_id}")
async def get_habit_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика по всем привычкам пользователя"""
    # Получить все привычки
    result = await db.execute(select(Habit).where(Habit.user_id == user_id))
    habits = result.scalars().all()
    
    if not habits:
        return {
            "user_id": user_id,
            "total_habits": 0,
            "total_completions": 0,
            "by_frequency": {}
        }
    
    total_completions = 0
    habit_stats = []
    
    for habit in habits:
        # Подсчитать логи для каждой привычки
        result = await db.execute(
            select(sql_func.count(HabitLog.id))
            .where(HabitLog.habit_id == habit.id)
        )
        count = result.scalar() or 0
        total_completions += count
        
        habit_stats.append({
            "habit_id": habit.id,
            "name": habit.name,
            "completions": count
        })
    
    return {
        "user_id": user_id,
        "total_habits": len(habits),
        "total_completions": total_completions,
        "by_frequency": {
            "daily": sum(1 for h in habits if h.frequency == HabitFrequency.DAILY),
            "weekly": sum(1 for h in habits if h.frequency == HabitFrequency.WEEKLY),
            "monthly": sum(1 for h in habits if h.frequency == HabitFrequency.MONTHLY),
        },
        "habits": habit_stats
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

