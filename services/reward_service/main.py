"""
Reward Service - Централизованная выдача наград
Порт: 8011
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import logging

from services.shared.database import get_db, init_db
from services.shared.game_lives import add_lives, lives_for_source
from services.shared.migrations import apply_hackathon_migrations
from services.shared.models.economy import Transaction, TransactionType
from services.shared.character_mood import mood_from_satisfaction, growth_stage
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)

# Источники, для которых проверяются достижения посещаемости
ATTENDANCE_SOURCES = {"lesson_attendance"}

# Pydantic схемы
class RewardRequest(BaseModel):
    user_id: int
    coins: int = 0
    intelligence_points: int = 0
    satisfaction: int = 0
    item_id: Optional[int] = None
    item_quantity: int = 1
    # Откуда награда (lesson_attendance, task_completion, lesson_missed, ...) — пишется в журнал
    source: Optional[str] = None
    source_ref: Optional[str] = None
    # Проверять автоматическую разблокировку сетов кастомизации
    check_unlocks: bool = True

class RewardResponse(BaseModel):
    user_id: int
    coins_added: int
    intelligence_added: int
    satisfaction_added: int
    item_added: Optional[int] = None
    level_up: bool = False
    achievements_earned: list = []
    coins_total: Optional[int] = None
    character: Optional[Dict[str, Any]] = None
    unlocked_sets: List[Dict[str, Any]] = []
    lives_added: int = 0
    lives: Optional[int] = None

# FastAPI приложение
app = FastAPI(title="Reward Service", version="1.1.0")

@app.on_event("startup")
async def startup():
    await init_db()
    await apply_hackathon_migrations()

@app.get("/")
async def root():
    return {"service": "Reward Service", "version": "1.1.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}


async def _check_achievements(achievement_service: ServiceClient, user_id: int, requirement_type: str) -> list:
    try:
        result = await achievement_service.post(
            f"/achievements/users/{user_id}/check",
            params={"requirement_type": requirement_type}
        )
        if isinstance(result, dict) and isinstance(result.get("newly_completed"), list):
            return result["newly_completed"]
    except Exception as e:
        logger.warning("Проверка достижений %s не удалась: %s", requirement_type, e)
    return []


async def _write_ledger(db: AsyncSession, reward_req: RewardRequest) -> None:
    """Журнал начислений (transactions): используется дашбордом куратора и для аудита"""
    if reward_req.coins == 0 and not reward_req.source:
        return
    parts = []
    if reward_req.coins:
        parts.append(f"монеты {reward_req.coins:+d}")
    if reward_req.intelligence_points:
        parts.append(f"интеллект {reward_req.intelligence_points:+d}")
    if reward_req.satisfaction:
        parts.append(f"удовлетворение {reward_req.satisfaction:+d}")
    try:
        db.add(Transaction(
            user_id=reward_req.user_id,
            type=TransactionType.REWARD,
            amount=reward_req.coins,
            description=", ".join(parts) or "награда",
            source=reward_req.source,
            source_ref=reward_req.source_ref,
        ))
        await db.commit()
    except Exception as e:
        await db.rollback()
        logger.warning("Не удалось записать награду в журнал: %s", e)


@app.post("/rewards/grant", response_model=RewardResponse)
async def grant_rewards(reward_req: RewardRequest, db: AsyncSession = Depends(get_db)):
    """
    Централизованная выдача всех наград
    """
    user_service = ServiceClient("user")
    character_service = ServiceClient("character")
    inventory_service = ServiceClient("inventory")
    achievement_service = ServiceClient("achievement")

    response = RewardResponse(
        user_id=reward_req.user_id,
        coins_added=0,
        intelligence_added=0,
        satisfaction_added=0,
        level_up=False,
        achievements_earned=[]
    )

    try:
        # 1. Выдача монет
        if reward_req.coins != 0:
            if reward_req.coins > 0:
                coins_result = await user_service.post(
                    f"/users/{reward_req.user_id}/coins/add",
                    json={"amount": reward_req.coins}
                )
            else:
                coins_result = await user_service.post(
                    f"/users/{reward_req.user_id}/coins/subtract",
                    json={"amount": abs(reward_req.coins)}
                )
            response.coins_added = reward_req.coins
            if isinstance(coins_result, dict) and isinstance(coins_result.get("coins"), int):
                response.coins_total = coins_result["coins"]

        character_id = None
        character_state: Dict[str, Any] = {}
        if reward_req.intelligence_points != 0 or reward_req.satisfaction != 0 or reward_req.source:
            character_data = await character_service.get(f"/characters/user/{reward_req.user_id}")
            character_id = character_data.get("id") if character_data else None
            if not character_id:
                raise HTTPException(status_code=404, detail="Персонаж не найден")
            before = character_data.get("satisfaction")
            character_state = {
                "satisfaction_before": before,
                "satisfaction": before,
                "intelligence_level": character_data.get("intelligence_level"),
                "intelligence_points": character_data.get("intelligence_points"),
            }

        # 2. Выдача очков интеллекта
        if reward_req.intelligence_points != 0 and character_id:
            intel_response = await character_service.post(
                f"/characters/{character_id}/intelligence/add",
                json={"points": reward_req.intelligence_points}
            )
            response.intelligence_added = reward_req.intelligence_points
            response.level_up = intel_response.get("level_up", False) if intel_response else False
            if isinstance(intel_response, dict):
                for key in ("intelligence_level", "intelligence_points"):
                    if key in intel_response:
                        character_state[key] = intel_response[key]

        # 3. Выдача удовлетворенности
        if reward_req.satisfaction != 0 and character_id:
            sat_response = await character_service.post(
                f"/characters/{character_id}/satisfaction/adjust",
                params={"amount": reward_req.satisfaction}
            )
            response.satisfaction_added = reward_req.satisfaction
            if isinstance(sat_response, dict) and isinstance(sat_response.get("satisfaction"), int):
                character_state["satisfaction"] = sat_response["satisfaction"]

        # 4. Выдача предметов
        if reward_req.item_id:
            await inventory_service.post(
                f"/items/add-to-user/{reward_req.user_id}",
                json={"item_id": reward_req.item_id, "quantity": reward_req.item_quantity}
            )
            response.item_added = reward_req.item_id

        if character_state:
            character_state["level_up"] = response.level_up
            if isinstance(character_state.get("satisfaction"), int):
                mood, mood_label = mood_from_satisfaction(character_state["satisfaction"])
                character_state["mood"] = mood
                character_state["mood_label"] = mood_label
            if isinstance(character_state.get("intelligence_level"), int):
                character_state["growth_stage"] = growth_stage(character_state["intelligence_level"])[0]
            response.character = character_state

        # 5. Журнал начислений
        await _write_ledger(db, reward_req)

        # 6. Проверка достижений после выдачи наград
        newly_completed = []
        if reward_req.coins > 0:
            newly_completed.extend(await _check_achievements(achievement_service, reward_req.user_id, "coins_earned"))
        if reward_req.intelligence_points > 0:
            newly_completed.extend(await _check_achievements(achievement_service, reward_req.user_id, "intelligence_points_earned"))
        if reward_req.source in ATTENDANCE_SOURCES:
            newly_completed.extend(await _check_achievements(achievement_service, reward_req.user_id, "lessons_attended"))
            newly_completed.extend(await _check_achievements(achievement_service, reward_req.user_id, "attendance_streak"))
        response.achievements_earned = newly_completed

        # Жизнь за саму учёбу; отдельно — за достижение (source=achievement), без двойного счёта.
        life_bonus = lives_for_source(reward_req.source)
        if life_bonus > 0:
            try:
                granted = await add_lives(db, reward_req.user_id, life_bonus)
                response.lives_added = granted.get("lives_added", 0)
                response.lives = granted.get("lives")
            except Exception as e:
                logger.warning("Не удалось начислить жизни мини-игры: %s", e)

        # 7. Автоматическая разблокировка сетов кастомизации
        gained = reward_req.coins > 0 or reward_req.intelligence_points > 0 or reward_req.source in ATTENDANCE_SOURCES
        if reward_req.check_unlocks and gained:
            try:
                unlock_result = await character_service.post(
                    f"/characters/user/{reward_req.user_id}/appearance/check-unlocks"
                )
                if isinstance(unlock_result, dict) and isinstance(unlock_result.get("unlocked"), list):
                    response.unlocked_sets = unlock_result["unlocked"]
            except Exception as e:
                logger.warning("Проверка разблокировок не удалась: %s", e)

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче наград: {str(e)}")
    finally:
        await user_service.close()
        await character_service.close()
        await inventory_service.close()
        await achievement_service.close()

@app.post("/rewards/coins")
async def grant_coins(user_id: int, amount: int):
    """Выдать монеты пользователю"""
    user_service = ServiceClient("user")
    try:
        result = await user_service.post(
            f"/users/{user_id}/coins/add",
            json={"amount": amount}
        )
        return result
    finally:
        await user_service.close()

@app.post("/rewards/intelligence")
async def grant_intelligence(user_id: int, points: int):
    """Выдать очки интеллекта"""
    character_service = ServiceClient("character")
    try:
        # Получаем персонажа
        character_data = await character_service.get(f"/characters/user/{user_id}")
        character_id = character_data.get("id")

        # Добавляем очки
        result = await character_service.post(
            f"/characters/{character_id}/intelligence/add",
            json={"points": points}
        )
        return result
    finally:
        await character_service.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
