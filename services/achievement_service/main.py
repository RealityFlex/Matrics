"""
Achievement Service - Управление достижениями
Порт: 8006
"""
import logging
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func as sql_func
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from services.shared.database import get_db, init_db
from services.shared.models.achievement import Achievement, UserAchievement
from services.shared.models.user import User
from services.shared.utils import ServiceClient
from services.shared.realtime import push_user_event

# Настройка логирования
logger = logging.getLogger(__name__)

# Pydantic схемы
class AchievementCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    requirement_type: str = Field(..., min_length=1, max_length=50)
    requirement_value: int = Field(..., ge=1)
    reward_coins: int = Field(default=0, ge=0)
    reward_intelligence_points: int = Field(default=0, ge=0)
    is_hidden: bool = False

class AchievementUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    icon: Optional[str] = None
    requirement_value: Optional[int] = Field(None, ge=1)
    reward_coins: Optional[int] = Field(None, ge=0)
    reward_intelligence_points: Optional[int] = Field(None, ge=0)
    is_hidden: Optional[bool] = None

class AchievementResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    icon: Optional[str]
    requirement_type: str
    requirement_value: int
    reward_coins: int
    reward_intelligence_points: int
    is_hidden: bool
    
    class Config:
        from_attributes = True

class UserAchievementResponse(BaseModel):
    id: int
    user_id: int
    achievement_id: int
    progress: int
    completed: bool
    completed_at: Optional[datetime]
    achievement: AchievementResponse
    
    class Config:
        from_attributes = True

# FastAPI приложение
app = FastAPI(title="Achievement Service", version="1.0.0")

ATTENDANCE_ACHIEVEMENTS = [
    # name, description, icon, requirement_type, value, coins, intelligence
    ("Первый шаг", "Добро пожаловать в игру!", "🏆", "tasks_completed", 1, 100, 10),
    ("Первая пара", "Отметьтесь на первом занятии", "🎓", "lessons_attended", 1, 10, 5),
    ("Без пропусков", "Серия из 5 посещённых занятий подряд", "🔥", "attendance_streak", 5, 30, 20),
    ("Железная дисциплина", "Серия из 14 посещённых занятий подряд", "🏅", "attendance_streak", 14, 80, 50),
    ("Постоянный слушатель", "Посетите 20 занятий", "📚", "lessons_attended", 20, 60, 40),
]


async def seed_attendance_achievements() -> None:
    """Достижения за посещаемость (создаются один раз, по названию)"""
    from services.shared.database import AsyncSessionLocal

    try:
        async with AsyncSessionLocal() as session:
            existing = set((await session.execute(select(Achievement.name))).scalars().all())
            for name, description, icon, req_type, value, coins, intel in ATTENDANCE_ACHIEVEMENTS:
                if name not in existing:
                    session.add(Achievement(
                        name=name, description=description, icon=icon,
                        requirement_type=req_type, requirement_value=value,
                        reward_coins=coins, reward_intelligence_points=intel,
                    ))
            await session.commit()
    except Exception as e:
        logger.warning(f"Не удалось создать достижения посещаемости: {e}")


@app.on_event("startup")
async def startup():
    from services.shared.migrations import apply_hackathon_migrations

    await init_db()
    await apply_hackathon_migrations()
    await seed_attendance_achievements()

@app.get("/")
async def root():
    return {"service": "Achievement Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD достижений
@app.post("/achievements/", response_model=AchievementResponse, status_code=201)
async def create_achievement(
    achievement_in: AchievementCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать достижение"""
    # Проверка уникальности
    result = await db.execute(select(Achievement).where(Achievement.name == achievement_in.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Достижение с таким именем уже существует")
    
    achievement = Achievement(**achievement_in.model_dump())
    db.add(achievement)
    await db.commit()
    await db.refresh(achievement)
    return achievement

@app.get("/achievements/", response_model=List[AchievementResponse])
async def list_achievements(
    skip: int = 0,
    limit: int = 100,
    include_hidden: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Список всех достижений"""
    query = select(Achievement)
    if not include_hidden:
        query = query.where(Achievement.is_hidden == False)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@app.get("/achievements/{achievement_id}", response_model=AchievementResponse)
async def get_achievement(achievement_id: int, db: AsyncSession = Depends(get_db)):
    """Получить достижение по ID"""
    result = await db.execute(select(Achievement).where(Achievement.id == achievement_id))
    achievement = result.scalar_one_or_none()
    if not achievement:
        raise HTTPException(status_code=404, detail="Достижение не найдено")
    return achievement

@app.put("/achievements/{achievement_id}", response_model=AchievementResponse)
async def update_achievement(
    achievement_id: int,
    achievement_in: AchievementUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить достижение"""
    result = await db.execute(select(Achievement).where(Achievement.id == achievement_id))
    achievement = result.scalar_one_or_none()
    if not achievement:
        raise HTTPException(status_code=404, detail="Достижение не найдено")
    
    update_data = achievement_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(achievement, field, value)
    
    await db.commit()
    await db.refresh(achievement)
    return achievement

@app.delete("/achievements/{achievement_id}", response_model=AchievementResponse)
async def delete_achievement(achievement_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить достижение"""
    result = await db.execute(select(Achievement).where(Achievement.id == achievement_id))
    achievement = result.scalar_one_or_none()
    if not achievement:
        raise HTTPException(status_code=404, detail="Достижение не найдено")
    
    await db.delete(achievement)
    await db.commit()
    return achievement

# Достижения пользователя
@app.get("/achievements/users/{user_id}", response_model=List[UserAchievementResponse])
async def get_user_achievements(
    user_id: int,
    completed_only: bool = False,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить достижения пользователя"""
    query = select(UserAchievement).where(UserAchievement.user_id == user_id)
    
    if completed_only:
        query = query.where(UserAchievement.completed == True)
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    user_achievements = result.scalars().all()
    
    # Загрузить информацию о достижениях
    response = []
    for user_achievement in user_achievements:
        ach_result = await db.execute(
            select(Achievement).where(Achievement.id == user_achievement.achievement_id)
        )
        achievement = ach_result.scalar_one_or_none()
        if achievement:
            response.append(UserAchievementResponse(
                id=user_achievement.id,
                user_id=user_achievement.user_id,
                achievement_id=user_achievement.achievement_id,
                progress=user_achievement.progress,
                completed=user_achievement.completed,
                completed_at=user_achievement.completed_at,
                achievement=AchievementResponse.model_validate(achievement)
            ))
    
    return response

@app.post("/achievements/users/{user_id}/progress")
async def update_achievement_progress(
    user_id: int,
    achievement_id: int,
    increment: int = 1,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить прогресс достижения пользователя
    Если достижение выполнено - выдать награды
    """
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Получить достижение
    result = await db.execute(select(Achievement).where(Achievement.id == achievement_id))
    achievement = result.scalar_one_or_none()
    if not achievement:
        raise HTTPException(status_code=404, detail="Достижение не найдено")
    
    # Найти или создать запись о достижении пользователя
    result = await db.execute(
        select(UserAchievement).where(and_(
            UserAchievement.user_id == user_id,
            UserAchievement.achievement_id == achievement_id
        ))
    )
    user_achievement = result.scalar_one_or_none()
    
    if not user_achievement:
        user_achievement = UserAchievement(
            user_id=user_id,
            achievement_id=achievement_id,
            progress=0,
            completed=False
        )
        db.add(user_achievement)
        await db.commit()
    
    # Если уже выполнено - ничего не делать
    if user_achievement.completed:
        return {
            "user_id": user_id,
            "achievement_id": achievement_id,
            "already_completed": True,
            "progress": user_achievement.progress
        }
    
    # Обновить прогресс
    user_achievement.progress += increment
    
    # Проверить выполнение
    rewards_granted = None
    if user_achievement.progress >= achievement.requirement_value:
        user_achievement.completed = True
        user_achievement.completed_at = datetime.now()
        
        # Выдать награды через Reward Service
        reward_service = ServiceClient("reward")
        try:
            rewards_granted = await reward_service.post("/rewards/grant", json={
                "user_id": user_id,
                "coins": achievement.reward_coins,
                "intelligence_points": achievement.reward_intelligence_points,
                "source": "achievement",
                "source_ref": f"achievement:{achievement.id}",
                # Разблокировки проверит исходное начисление (иначе вложенный вызов «съест» их)
                "check_unlocks": False
            })
        except Exception as e:
            # Логируем ошибку, но не откатываем прогресс
            print(f"Ошибка при выдаче наград: {str(e)}")
        finally:
            await reward_service.close()
        await push_user_event(
            user_id,
            "achievements.completed",
            payload={
                "achievement_id": achievement.id,
                "achievement_name": achievement.name,
                "reward_coins": achievement.reward_coins,
                "reward_intelligence_points": achievement.reward_intelligence_points,
            },
            metadata={"source": "achievement_service"},
        )
    
    await db.commit()
    await db.refresh(user_achievement)
    
    return {
        "user_id": user_id,
        "achievement_id": achievement_id,
        "achievement_name": achievement.name,
        "progress": user_achievement.progress,
        "requirement": achievement.requirement_value,
        "completed": user_achievement.completed,
        "rewards": rewards_granted
    }

@app.post("/achievements/users/{user_id}/check")
async def check_achievements(
    user_id: int,
    requirement_type: str = Query(..., description="Тип требования для проверки"),
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить все достижения определенного типа для пользователя
    и обновить их прогресс
    """
    logger.info(f"Checking achievements for user {user_id}, requirement_type: {requirement_type}")
    # Получить все достижения этого типа
    result = await db.execute(
        select(Achievement).where(Achievement.requirement_type == requirement_type)
    )
    achievements = result.scalars().all()
    
    if not achievements:
        return {
            "user_id": user_id,
            "requirement_type": requirement_type,
            "checked": 0,
            "newly_completed": []
        }
    
    # Получить реальный прогресс из соответствующего сервиса
    current_progress = 0
    if requirement_type == "coins" or requirement_type == "coins_earned":
        # Для coins_earned используем текущий баланс монет как показатель заработанных
        # (если нет отдельного отслеживания заработанных монет)
        user_service = ServiceClient("user")
        try:
            user_data = await user_service.get(f"/users/{user_id}/coins")
            logger.info(f"DEBUG: user_data = {user_data}")
            current_progress = user_data.get("coins", 0) if isinstance(user_data, dict) else 0
            logger.info(f"DEBUG: current_progress = {current_progress} for user {user_id}, requirement_type = {requirement_type}")
        except Exception as e:
            logger.error(f"Ошибка получения монет пользователя: {str(e)}")
        finally:
            await user_service.close()
    elif requirement_type == "intelligence_points" or requirement_type == "intelligence_points_earned":
        # Для intelligence_points_earned используем текущее значение очков интеллекта
        # (если нет отдельного отслеживания заработанных очков)
        character_service = ServiceClient("character")
        try:
            character_data = await character_service.get(f"/characters/user/{user_id}")
            if isinstance(character_data, list) and len(character_data) > 0:
                character_data = character_data[0]
            current_progress = character_data.get("intelligence_points", 0) if character_data else 0
            logger.info(f"DEBUG: intelligence_points progress = {current_progress} for user {user_id}, requirement_type = {requirement_type}")
        except Exception as e:
            logger.error(f"Ошибка получения очков интеллекта: {str(e)}")
            current_progress = 0
        finally:
            await character_service.close()
    elif requirement_type == "tasks_completed":
        # Получаем количество выполненных задач из task_service
        task_service = ServiceClient("task")
        try:
            stats_data = await task_service.get(f"/tasks/stats/{user_id}")
            if isinstance(stats_data, dict):
                current_progress = stats_data.get("completed", 0)
            else:
                current_progress = 0
            logger.info(f"DEBUG: tasks_completed progress = {current_progress} for user {user_id}")
        except Exception as e:
            logger.error(f"Ошибка получения статистики задач: {str(e)}")
            current_progress = 0
        finally:
            await task_service.close()
    elif requirement_type in ("lessons_attended", "attendance_streak"):
        # Посещаемость занятий считается напрямую по общей БД
        from services.shared.streaks import get_attendance_streak

        try:
            streak = await get_attendance_streak(db, user_id)
            current_progress = streak["lessons_attended"] if requirement_type == "lessons_attended" else streak["best"]
        except Exception as e:
            logger.error(f"Ошибка расчёта посещаемости: {str(e)}")
            current_progress = 0
    # TODO: Добавить другие типы требований (habits_logged, events_attended и т.д.)
    
    newly_completed = []
    
    for achievement in achievements:
        # Получить текущий прогресс
        result = await db.execute(
            select(UserAchievement).where(and_(
                UserAchievement.user_id == user_id,
                UserAchievement.achievement_id == achievement.id
            ))
        )
        user_achievement = result.scalar_one_or_none()
        
        if not user_achievement:
            user_achievement = UserAchievement(
                user_id=user_id,
                achievement_id=achievement.id,
                progress=0,
                completed=False
            )
            db.add(user_achievement)
            await db.commit()
        
        # Обновить прогресс (даже если достижение уже выполнено, чтобы правильно отображать статистику)
        # Для достижений типа "coins_earned" или "coins" используем текущий баланс
        # Для завершенных достижений не позволяем прогрессу опускаться ниже требования
        if user_achievement.completed:
            # Если достижение уже завершено, прогресс должен быть не меньше требования
            user_achievement.progress = max(current_progress, achievement.requirement_value)
        else:
            user_achievement.progress = current_progress
        logger.info(f"DEBUG: Updated progress for achievement {achievement.id}: {user_achievement.progress} (requirement: {achievement.requirement_value}, completed: {user_achievement.completed})")
        
        # Проверить выполнение (только если еще не выполнено)
        if not user_achievement.completed and user_achievement.progress >= achievement.requirement_value:
            logger.info(f"DEBUG: Achievement {achievement.id} completed!")
            user_achievement.completed = True
            user_achievement.completed_at = datetime.now()
            
            # Выдать награды через Reward Service
            reward_service = ServiceClient("reward")
            try:
                await reward_service.post("/rewards/grant", json={
                    "user_id": user_id,
                    "coins": achievement.reward_coins,
                    "intelligence_points": achievement.reward_intelligence_points,
                    "source": "achievement",
                    "source_ref": f"achievement:{achievement.id}",
                    # Разблокировки проверит исходное начисление (иначе вложенный вызов «съест» их)
                    "check_unlocks": False
                })
            except Exception as e:
                logger.error(f"Ошибка при выдаче наград: {str(e)}")
            finally:
                await reward_service.close()
            
            newly_completed.append({
                "achievement_id": achievement.id,
                "achievement_name": achievement.name
            })
            await push_user_event(
                user_id,
                "achievements.completed",
                payload={
                    "achievement_id": achievement.id,
                    "achievement_name": achievement.name,
                    "reward_coins": achievement.reward_coins,
                    "reward_intelligence_points": achievement.reward_intelligence_points,
                },
                metadata={"source": "achievement_service"},
            )
        
        await db.commit()
    
    # Больше не нужен второй commit
    
    return {
        "user_id": user_id,
        "requirement_type": requirement_type,
        "checked": len(achievements),
        "newly_completed": newly_completed
    }

@app.get("/achievements/stats/{user_id}")
async def get_achievement_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика по достижениям пользователя"""
    # Получить все достижения пользователя
    result = await db.execute(
        select(UserAchievement).where(UserAchievement.user_id == user_id)
    )
    user_achievements = result.scalars().all()
    
    # Подсчитать общее количество достижений
    result = await db.execute(select(sql_func.count(Achievement.id)))
    total_achievements = result.scalar()
    
    completed_count = sum(1 for ua in user_achievements if ua.completed)
    
    return {
        "user_id": user_id,
        "total_achievements": total_achievements,
        "completed": completed_count,
        "in_progress": len(user_achievements) - completed_count,
        "completion_rate": round(completed_count / total_achievements * 100, 2) if total_achievements > 0 else 0
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)

