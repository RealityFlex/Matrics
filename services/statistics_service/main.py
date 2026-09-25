"""
Statistics Service - Агрегация статистики со всех сервисов
Порт: 8012
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Dict, Any
from pydantic import BaseModel

from services.shared.database import get_db, init_db
from services.shared.models.user import User
# Импортируем TaskGeneration для корректной инициализации relationship в User
from services.shared.models.task_generation import TaskGeneration
from services.shared.utils import ServiceClient
from services.shared.models.character import Character
from services.shared.migrations import apply_hackathon_migrations
from services.statistics_service import curator

# FastAPI приложение
app = FastAPI(title="Statistics Service", version="1.0.0")

@app.on_event("startup")
async def startup():
    await init_db()
    await apply_hackathon_migrations()
    import asyncio

    asyncio.create_task(curator.digest_worker())

# Дашборд куратора (read-only)
app.include_router(curator.router)

@app.get("/")
async def root():
    return {"service": "Statistics Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/stats/users/{user_id}/summary")
async def get_user_summary_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить сводную статистику пользователя со всех сервисов
    """
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    summary = {
        "user_id": user_id,
        "username": user.username,
        "email": user.email
    }
    
    # Получить данные персонажа
    character_service = ServiceClient("character")
    try:
        character_result = await character_service.get(f"/characters/user/{user_id}")
        if character_result:
            character = character_result[0] if isinstance(character_result, list) and character_result else character_result
            summary["character"] = {
                "satisfaction": character.get("satisfaction"),
                "intelligence_level": character.get("intelligence_level"),
                "intelligence_points": character.get("intelligence_points"),
                "coins": user.coins,  # Монеты берутся из user, а не из character
                "rating": character.get("rating"),
                "bonus_points": character.get("bonus_points")
            }
    except Exception as e:
        summary["character"] = {"error": str(e)}
    finally:
        await character_service.close()
    
    # Получить статистику задач
    task_service = ServiceClient("task")
    try:
        task_stats = await task_service.get(f"/tasks/stats/{user_id}")
        summary["tasks"] = task_stats
    except Exception as e:
        summary["tasks"] = {"error": str(e)}
    finally:
        await task_service.close()
    
    # Получить статистику привычек
    habit_service = ServiceClient("habit")
    try:
        habit_stats = await habit_service.get(f"/habits/stats/{user_id}")
        summary["habits"] = habit_stats
    except Exception as e:
        summary["habits"] = {"error": str(e)}
    finally:
        await habit_service.close()
    
    # Получить инвентарь
    inventory_service = ServiceClient("inventory")
    try:
        inventory = await inventory_service.get(f"/inventory/users/{user_id}")
        summary["inventory"] = {
            "total_items": len(inventory) if inventory else 0
        }
    except Exception as e:
        summary["inventory"] = {"error": str(e)}
    finally:
        await inventory_service.close()
    
    # Получить статистику достижений
    achievement_service = ServiceClient("achievement")
    try:
        achievement_stats = await achievement_service.get(f"/achievements/stats/{user_id}")
        summary["achievements"] = achievement_stats
    except Exception as e:
        summary["achievements"] = {"error": str(e)}
    finally:
        await achievement_service.close()
    
    # Получить статистику событий
    event_service = ServiceClient("event")
    try:
        event_stats = await event_service.get(f"/events/stats/{user_id}")
        summary["events"] = event_stats
    except Exception as e:
        summary["events"] = {"error": str(e)}
    finally:
        await event_service.close()
    
    # Получить статистику соревнований
    competition_service = ServiceClient("competition")
    try:
        competition_stats = await competition_service.get(f"/competitions/stats/{user_id}")
        summary["competitions"] = competition_stats
    except Exception as e:
        summary["competitions"] = {"error": str(e)}
    finally:
        await competition_service.close()
    
    return summary

@app.get("/stats/users/{user_id}/detailed")
async def get_user_detailed_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить детальную статистику пользователя со всех сервисов
    """
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    detailed = {
        "user_id": user_id,
        "username": user.username,
        "email": user.email
    }
    
    # Получить список всех задач
    task_service = ServiceClient("task")
    try:
        tasks = await task_service.get(f"/tasks/user/{user_id}")
        detailed["tasks"] = tasks
    except Exception as e:
        detailed["tasks"] = {"error": str(e)}
    finally:
        await task_service.close()
    
    # Получить список всех привычек
    habit_service = ServiceClient("habit")
    try:
        habits = await habit_service.get(f"/habits/user/{user_id}")
        detailed["habits"] = habits
    except Exception as e:
        detailed["habits"] = {"error": str(e)}
    finally:
        await habit_service.close()
    
    # Получить все предметы инвентаря
    inventory_service = ServiceClient("inventory")
    try:
        inventory = await inventory_service.get(f"/inventory/users/{user_id}")
        detailed["inventory"] = inventory
    except Exception as e:
        detailed["inventory"] = {"error": str(e)}
    finally:
        await inventory_service.close()
    
    # Получить все достижения
    achievement_service = ServiceClient("achievement")
    try:
        achievements = await achievement_service.get(f"/achievements/users/{user_id}")
        detailed["achievements"] = achievements
    except Exception as e:
        detailed["achievements"] = {"error": str(e)}
    finally:
        await achievement_service.close()
    
    # Получить события пользователя
    event_service = ServiceClient("event")
    try:
        events = await event_service.get(f"/events/users/{user_id}")
        detailed["events"] = events
    except Exception as e:
        detailed["events"] = {"error": str(e)}
    finally:
        await event_service.close()
    
    # Получить соревнования пользователя
    competition_service = ServiceClient("competition")
    try:
        competitions = await competition_service.get(f"/competitions/users/{user_id}")
        detailed["competitions"] = competitions
    except Exception as e:
        detailed["competitions"] = {"error": str(e)}
    finally:
        await competition_service.close()
    
    # Получить транзакции пользователя
    economy_service = ServiceClient("economy")
    try:
        transactions = await economy_service.get(f"/transactions/users/{user_id}", params={"limit": 50})
        detailed["recent_transactions"] = transactions
    except Exception as e:
        detailed["recent_transactions"] = {"error": str(e)}
    finally:
        await economy_service.close()
    
    return detailed

@app.get("/stats/global/overview")
async def get_global_overview():
    """
    Получить глобальную статистику системы
    """
    overview = {}
    
    # Статистика пользователей
    user_service = ServiceClient("user")
    try:
        users = await user_service.get("/users/", params={"limit": 1000})
        overview["total_users"] = len(users) if users else 0
    except Exception as e:
        overview["total_users"] = {"error": str(e)}
    finally:
        await user_service.close()
    
    # Статистика задач
    task_service = ServiceClient("task")
    try:
        tasks = await task_service.get("/tasks/", params={"limit": 1000})
        overview["total_tasks"] = len(tasks) if tasks else 0
    except Exception as e:
        overview["total_tasks"] = {"error": str(e)}
    finally:
        await task_service.close()
    
    # Статистика привычек
    habit_service = ServiceClient("habit")
    try:
        habits = await habit_service.get("/habits/", params={"limit": 1000})
        overview["total_habits"] = len(habits) if habits else 0
    except Exception as e:
        overview["total_habits"] = {"error": str(e)}
    finally:
        await habit_service.close()
    
    # Статистика предметов
    inventory_service = ServiceClient("inventory")
    try:
        items = await inventory_service.get("/items/", params={"limit": 1000})
        overview["total_items"] = len(items) if items else 0
    except Exception as e:
        overview["total_items"] = {"error": str(e)}
    finally:
        await inventory_service.close()
    
    # Статистика достижений
    achievement_service = ServiceClient("achievement")
    try:
        achievements = await achievement_service.get("/achievements/", params={"limit": 1000})
        overview["total_achievements"] = len(achievements) if achievements else 0
    except Exception as e:
        overview["total_achievements"] = {"error": str(e)}
    finally:
        await achievement_service.close()
    
    # Статистика событий
    event_service = ServiceClient("event")
    try:
        events = await event_service.get("/events/", params={"limit": 1000})
        overview["total_events"] = len(events) if events else 0
    except Exception as e:
        overview["total_events"] = {"error": str(e)}
    finally:
        await event_service.close()
    
    # Статистика соревнований
    competition_service = ServiceClient("competition")
    try:
        competitions = await competition_service.get("/competitions/", params={"limit": 1000})
        overview["total_competitions"] = len(competitions) if competitions else 0
    except Exception as e:
        overview["total_competitions"] = {"error": str(e)}
    finally:
        await competition_service.close()
    
    # Статистика кланов
    social_service = ServiceClient("social")
    try:
        clans = await social_service.get("/clans/", params={"limit": 1000})
        overview["total_clans"] = len(clans) if clans else 0
    except Exception as e:
        overview["total_clans"] = {"error": str(e)}
    finally:
        await social_service.close()
    
    return overview

@app.get("/stats/leaderboard/rating")
async def get_rating_leaderboard(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Получить топ пользователей по рейтингу (прямой запрос к общей БД)
    """
    rows = (await db.execute(
        select(User.id, User.username, Character).join(Character, Character.user_id == User.id)
    )).all()
    leaderboard = [
        {
            "user_id": user_id,
            "username": username,
            "rating": character.rating,
            "satisfaction": character.satisfaction,
            "intelligence_level": character.intelligence_level,
        }
        for user_id, username, character in rows
    ]
    leaderboard.sort(key=lambda x: x["rating"], reverse=True)
    return leaderboard[:limit]

@app.get("/stats/leaderboard/coins")
async def get_coins_leaderboard(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """
    Получить топ пользователей по монетам
    """
    rows = (await db.execute(
        select(User.id, User.username, User.coins).order_by(User.coins.desc()).limit(limit)
    )).all()
    return [{"user_id": r[0], "username": r[1], "coins": r[2]} for r in rows]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8012)

