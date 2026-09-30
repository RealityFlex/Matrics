"""
Task Service - Управление задачами
Порт: 8003
"""
import asyncio
import logging
import os
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator
import re

from services.shared.database import get_db, init_db
from services.shared.migrations import apply_hackathon_migrations
from services.shared.models.task import Task, TaskStatus, TaskPriority, Goal, GoalTask, GoalStatus
from services.shared.models.user import User
from services.shared.models.task_generation import TaskGeneration
from services.shared.utils import ServiceClient
from services.task_service.ai_evaluator import TaskComplexityEvaluator
from services.task_service.goal_graph import dump_depends_on, parse_depends_on

logger = logging.getLogger(__name__)

# Оценка задач: GigaChat по умолчанию (LLM_PROVIDER=gigachat).
# Нужен GIGACHAT_CREDENTIALS из кабинета Sber. Запасные: openrouter, ollama.
complexity_evaluator = TaskComplexityEvaluator()
(
    STUB_REWARD_COINS,
    STUB_REWARD_INTELLIGENCE,
    STUB_REWARD_SATISFACTION,
) = complexity_evaluator.get_stub_rewards()

LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "40"))
MAX_COIN_REWARD = 50
MAX_INTELLIGENCE_REWARD = 15
MAX_SATISFACTION_REWARD = 20
MIN_SATISFACTION_FOR_REWARD = 3
SATISFACTION_FROM_COINS_FACTOR = 0.4

# Pydantic схемы
class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    priority: TaskPriority = TaskPriority.MEDIUM
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    due_date: Optional[datetime] = None
    # reward_coins нельзя изменять вручную - он вычисляется автоматически

class TaskResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    priority: TaskPriority
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int
    
    class Config:
        from_attributes = True


class GoalTaskResponse(BaseModel):
    id: int
    goal_id: int
    user_id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int
    order_index: int
    depends_on: List[int] = []
    due_date: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]

    @field_validator("depends_on", mode="before")
    @classmethod
    def _parse_depends_on(cls, value):
        return parse_depends_on(value)

    class Config:
        from_attributes = True


class GoalResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str]
    status: GoalStatus
    due_date: Optional[datetime]
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int
    created_at: datetime
    updated_at: Optional[datetime]
    completed_at: Optional[datetime]
    tasks: List[GoalTaskResponse] = []

    class Config:
        from_attributes = True


class GoalCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    due_date: Optional[datetime] = None


class GoalUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[GoalStatus] = None
    due_date: Optional[datetime] = None


class GoalTaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[TaskStatus] = None
    due_date: Optional[datetime] = None


async def _assess_and_reward(
    title: str,
    description: Optional[str] = None,
    priority: Optional[str] = None,
) -> tuple[bool, tuple[int, int, int]]:
    """Проверка корректности и оценка награды через GigaChat (или запасной LLM)."""
    try:
        priority_value = priority.value if isinstance(priority, TaskPriority) else priority
        assessment = await asyncio.wait_for(
            complexity_evaluator.assess_task(
                title=title,
                description=description,
                priority=priority_value,
            ),
            timeout=LLM_TIMEOUT_SECONDS,
        )
        if assessment.get("is_spam"):
            return True, (0, 0, 0)
        return False, _normalize_reward_values(
            assessment.get("reward_coins") or 0,
            assessment.get("reward_intelligence") or 0,
            assessment.get("reward_satisfaction") or 0,
        )
    except Exception as exc:
        logger.warning(
            "Оценка задачи через LLM не удалась (%s: %s). Используем запасные награды.",
            type(exc).__name__,
            exc or repr(exc),
        )
        return False, _get_stub_rewards()


async def _calculate_task_rewards(
    title: str,
    description: Optional[str] = None,
    priority: Optional[str] = None
) -> tuple[int, int, int]:
    _, rewards = await _assess_and_reward(title, description, priority)
    return rewards


def _normalize_reward_values(coins: int, intelligence: int, satisfaction: int) -> tuple[int, int, int]:
    coins = max(0, min(MAX_COIN_REWARD, int(coins or 0)))
    intelligence = max(0, min(MAX_INTELLIGENCE_REWARD, int(intelligence or 0)))
    satisfaction = max(0, min(MAX_SATISFACTION_REWARD, int(satisfaction or 0)))

    if coins <= 0:
        return 0, 0, 0

    target_intelligence = max(1, min(MAX_INTELLIGENCE_REWARD, round(coins * 0.3)))
    intelligence = max(target_intelligence, intelligence)

    min_satisfaction = max(MIN_SATISFACTION_FOR_REWARD, int(round(coins * SATISFACTION_FROM_COINS_FACTOR)))
    satisfaction = max(min_satisfaction, satisfaction)

    satisfaction = min(MAX_SATISFACTION_REWARD, satisfaction)

    return coins, intelligence, satisfaction


def _has_meaningful_text(text: Optional[str]) -> bool:
    if not text:
        return False
    cleaned = re.sub(r"[^A-Za-zА-Яа-я0-9]+", "", text)
    return len(cleaned.strip()) >= 3


def _get_stub_rewards() -> tuple[int, int, int]:
    return _normalize_reward_values(
        STUB_REWARD_COINS,
        STUB_REWARD_INTELLIGENCE,
        STUB_REWARD_SATISFACTION,
    )


async def _determine_task_rewards(
    title: str,
    description: Optional[str] = None,
    priority: Optional[TaskPriority] = None
) -> tuple[int, int, int]:
    """Награды за задачу: оценка модели или запасные значения."""
    _, rewards = await _assess_and_reward(
        title,
        description,
        priority.value if isinstance(priority, TaskPriority) else priority,
    )
    return rewards


async def _ensure_goal_exists(db: AsyncSession, goal_id: int) -> Goal:
    result = await db.execute(
        select(Goal).options(selectinload(Goal.tasks)).where(Goal.id == goal_id)
    )
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Цель не найдена")
    return goal


async def _refresh_goal_with_tasks(db: AsyncSession, goal: Goal) -> Goal:
    await db.refresh(goal)
    await db.refresh(goal, ["tasks"])
    return goal


async def _complete_goal(goal: Goal, db: AsyncSession) -> dict:
    if goal.status == GoalStatus.COMPLETED.value:
        raise HTTPException(status_code=400, detail="Цель уже завершена")

    incomplete = [
        task
        for task in goal.tasks
        if task.status != TaskStatus.COMPLETED.value
    ]
    if incomplete:
        raise HTTPException(
            status_code=400,
            detail="Невозможно завершить цель, пока не выполнены все подзадачи"
        )

    goal.status = GoalStatus.COMPLETED.value
    goal.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(goal)

    reward_service = ServiceClient("reward")
    try:
        rewards = await reward_service.post(
            "/rewards/grant",
            json={
                "user_id": goal.user_id,
                "coins": goal.reward_coins,
                "intelligence_points": goal.reward_intelligence_points,
                "satisfaction": goal.reward_satisfaction
            }
        )
    except Exception as exc:
        # Откат в случае ошибки награждения
        goal.status = GoalStatus.IN_PROGRESS.value
        goal.completed_at = None
        await db.flush()
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче награды за цель: {exc}")
    finally:
        await reward_service.close()

    return rewards

# FastAPI приложение
app = FastAPI(title="Task Service", version="1.0.0")

@app.on_event("startup")
async def startup():
    await init_db()
    await apply_hackathon_migrations()

@app.get("/")
async def root():
    return {"service": "Task Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD эндпоинты
@app.post("/tasks/", response_model=TaskResponse, status_code=201)
async def create_task(
    task_in: TaskCreate,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать задачу для пользователя.
    Стоимость в монетах (reward_coins) автоматически вычисляется через нейронную сеть
    в зависимости от сложности задачи (от 0 до 50 монет).
    """
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    title = task_in.title.strip()
    if not _has_meaningful_text(title):
        raise HTTPException(status_code=400, detail="Название задачи должно быть более осмысленным")
    description = task_in.description.strip() if task_in.description else None
    try:
        is_spam, (reward_coins, reward_intelligence_points, reward_satisfaction) = await _assess_and_reward(
            title=title,
            description=description,
            priority=task_in.priority,
        )
    except Exception as reward_exc:
        logger.error("Ошибка при оценке задачи '%s': %s", title, reward_exc, exc_info=True)
        is_spam = False
        reward_coins, reward_intelligence_points, reward_satisfaction = _get_stub_rewards()

    if is_spam:
        reward_coins = reward_intelligence_points = reward_satisfaction = 0
    
    # Создаем задачу с автоматически вычисленной стоимостью
    try:
        task_data = task_in.model_dump()
        task_data["title"] = title
        task_data["description"] = description
        task_data["reward_coins"] = reward_coins
        task_data["reward_intelligence_points"] = reward_intelligence_points
        task_data["reward_satisfaction"] = reward_satisfaction
        task = Task(**task_data, user_id=user_id)
        db.add(task)
        await db.commit()
        await db.refresh(task)
        return task
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка при создании задачи для пользователя {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка при создании задачи: {str(e)}")


@app.post("/tasks/goals/", response_model=GoalResponse, status_code=201)
async def create_goal(
    goal_in: GoalCreate,
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """
    Создать глобальную цель. Подзадачи автоматически генерируются через LLM.
    """
    # Проверка пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    goal_title = goal_in.title.strip()
    goal_description = goal_in.description.strip() if goal_in.description else None

    if not _has_meaningful_text(goal_title):
        raise HTTPException(status_code=400, detail="Название цели должно быть более осмысленным")

    try:
        is_spam, (reward_coins, reward_intelligence, reward_satisfaction) = await _assess_and_reward(
            title=goal_title,
            description=goal_description,
        )
    except Exception as spam_exc:
        logger.warning("Не удалось оценить цель: %s", spam_exc)
        is_spam = False
        reward_coins, reward_intelligence, reward_satisfaction = _get_stub_rewards()

    if is_spam:
        raise HTTPException(status_code=400, detail="Цель отмечена как спам")

    goal = Goal(
        user_id=user_id,
        title=goal_title,
        description=goal_description,
        due_date=goal_in.due_date,
        reward_coins=reward_coins,
        reward_intelligence_points=reward_intelligence,
        reward_satisfaction=reward_satisfaction,
        status=GoalStatus.PLANNED.value
    )
    db.add(goal)
    await db.commit()

    generated_tasks = await complexity_evaluator.generate_goal_breakdown(
        title=goal_title,
        description=goal_description
    )

    for item in generated_tasks:
        sub_title = item.get("title", "").strip()
        if not sub_title:
            continue
        sub_description = item.get("description", "").strip() or None
        if all(item.get(key) is not None for key in ("reward_coins", "reward_intelligence", "reward_satisfaction")):
            coins, intelligence, satisfaction = _normalize_reward_values(
                item.get("reward_coins") or 0,
                item.get("reward_intelligence") or 0,
                item.get("reward_satisfaction") or 0,
            )
        else:
            coins, intelligence, satisfaction = await _calculate_task_rewards(
                title=sub_title,
                description=sub_description
            )
        goal_task = GoalTask(
            goal_id=goal.id,
            user_id=user_id,
            title=sub_title,
            description=sub_description,
            reward_coins=coins,
            reward_intelligence_points=intelligence,
            reward_satisfaction=satisfaction,
            order_index=item.get("order_index", 0),
            depends_on=dump_depends_on(item.get("depends_on")),
            status=TaskStatus.TODO.value
        )
        db.add(goal_task)

    await db.commit()
    await _refresh_goal_with_tasks(db, goal)

    return GoalResponse.model_validate(goal)


@app.get("/tasks/goals/users/{user_id}", response_model=List[GoalResponse])
async def list_user_goals(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Получить список целей пользователя.
    """
    result = await db.execute(
        select(Goal)
        .options(selectinload(Goal.tasks))
        .where(Goal.user_id == user_id)
        .order_by(Goal.created_at.desc())
    )
    goals = result.scalars().all()
    return [GoalResponse.model_validate(goal) for goal in goals]


@app.get("/tasks/goals/{goal_id}", response_model=GoalResponse)
async def get_goal(goal_id: int, db: AsyncSession = Depends(get_db)):
    """
    Получить цель по ID.
    """
    goal = await _ensure_goal_exists(db, goal_id)
    return GoalResponse.model_validate(goal)


@app.put("/tasks/goals/{goal_id}", response_model=GoalResponse)
async def update_goal(
    goal_id: int,
    goal_in: GoalUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить цель. Если меняются название или описание – награды пересчитываются.
    """
    goal = await _ensure_goal_exists(db, goal_id)
    update_data = goal_in.model_dump(exclude_unset=True)

    if "title" in update_data:
        update_data["title"] = update_data["title"].strip()
        if update_data["title"] and not _has_meaningful_text(update_data["title"]):
            raise HTTPException(status_code=400, detail="Название цели должно быть более осмысленным")
    if "description" in update_data and update_data["description"] is not None:
        update_data["description"] = update_data["description"].strip()
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = (
            update_data["status"].value
            if isinstance(update_data["status"], GoalStatus)
            else str(update_data["status"])
        )

    reward_recalculate = any(field in update_data for field in ["title", "description"])

    for field, value in update_data.items():
        setattr(goal, field, value)

    if reward_recalculate:
        is_spam, (coins, intelligence, satisfaction) = await _assess_and_reward(
            title=goal.title,
            description=goal.description,
        )
        if is_spam:
            raise HTTPException(status_code=400, detail="Цель отмечена как спам")
        goal.reward_coins = coins
        goal.reward_intelligence_points = intelligence
        goal.reward_satisfaction = satisfaction

    if goal_in.status == GoalStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail="Используйте отдельный эндпоинт /goals/{goal_id}/complete для завершения цели"
        )

    await db.commit()
    await _refresh_goal_with_tasks(db, goal)

    return GoalResponse.model_validate(goal)


@app.delete("/tasks/goals/{goal_id}", response_model=GoalResponse)
async def delete_goal(goal_id: int, db: AsyncSession = Depends(get_db)):
    """
    Удалить цель вместе с подзадачами.
    """
    goal = await _ensure_goal_exists(db, goal_id)
    await db.delete(goal)
    return GoalResponse.model_validate(goal)


@app.put("/tasks/goals/{goal_id}/tasks/{task_id}")
async def update_goal_task(
    goal_id: int,
    task_id: int,
    task_in: GoalTaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить подзадачу в цели. При завершении выдается награда.
    """
    goal = await _ensure_goal_exists(db, goal_id)
    result = await db.execute(
        select(GoalTask).where(
            and_(
                GoalTask.id == task_id,
                GoalTask.goal_id == goal_id
            )
        )
    )
    goal_task = result.scalar_one_or_none()
    if not goal_task:
        raise HTTPException(status_code=404, detail="Подзадача не найдена")

    update_data = task_in.model_dump(exclude_unset=True)
    if "title" in update_data and update_data["title"]:
        update_data["title"] = update_data["title"].strip()
    if "description" in update_data and update_data["description"] is not None:
        update_data["description"] = update_data["description"].strip()
    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = (
            update_data["status"].value
            if isinstance(update_data["status"], TaskStatus)
            else str(update_data["status"])
        )

    reward_recalculate = any(field in update_data for field in ["title", "description"])

    previous_status = goal_task.status
    for field, value in update_data.items():
        setattr(goal_task, field, value)

    if reward_recalculate:
        coins, intelligence, satisfaction = await _calculate_task_rewards(
            title=goal_task.title,
            description=goal_task.description
        )
        coins, intelligence, satisfaction = _normalize_reward_values(coins, intelligence, satisfaction)
        goal_task.reward_coins = coins
        goal_task.reward_intelligence_points = intelligence
        goal_task.reward_satisfaction = satisfaction

    reward_payload = None
    new_status = update_data.get("status")
    if (
        new_status == TaskStatus.COMPLETED.value
        and previous_status != TaskStatus.COMPLETED.value
    ):
        goal_task.completed_at = datetime.now(timezone.utc)
        await db.commit()
        reward_service = ServiceClient("reward")
        try:
            reward_payload = await reward_service.post(
                "/rewards/grant",
                json={
                    "user_id": goal_task.user_id,
                    "coins": goal_task.reward_coins,
                    "intelligence_points": goal_task.reward_intelligence_points,
                    "satisfaction": goal_task.reward_satisfaction
                }
            )
            
            # Проверить достижения после завершения задачи
            achievement_service = ServiceClient("achievement")
            try:
                await achievement_service.post(
                    f"/achievements/users/{goal_task.user_id}/check",
                    params={"requirement_type": "tasks_completed"}
                )
                logger.info(f"Проверка достижений для пользователя {goal_task.user_id} после завершения подзадачи {task_id}")
            except Exception as e:
                # Логируем ошибку, но не прерываем выполнение
                logger.error(f"Ошибка при проверке достижений: {str(e)}")
            finally:
                await achievement_service.close()
        except Exception as exc:
            goal_task.status = previous_status
            goal_task.completed_at = None
            await db.commit()
            raise HTTPException(status_code=500, detail=f"Ошибка при выдаче награды за подзадачу: {exc}")
        finally:
            await reward_service.close()

    elif new_status and new_status != TaskStatus.COMPLETED.value:
        goal_task.completed_at = None

    await db.commit()
    await db.refresh(goal_task)
    await _refresh_goal_with_tasks(db, goal)

    # Обновляем статус цели в зависимости от прогресса
    if goal.status != GoalStatus.COMPLETED.value:
        if all(task.status == TaskStatus.COMPLETED.value for task in goal.tasks):
            goal.status = GoalStatus.IN_PROGRESS.value
        elif any(task.status != TaskStatus.TODO.value for task in goal.tasks):
            goal.status = GoalStatus.IN_PROGRESS.value
        else:
            goal.status = GoalStatus.PLANNED.value
        await db.commit()
        await _refresh_goal_with_tasks(db, goal)

    task_response = GoalTaskResponse.model_validate(goal_task)
    return {
        "task": task_response,
        "rewards": reward_payload
    }


@app.post("/tasks/goals/{goal_id}/complete")
async def complete_goal(goal_id: int, db: AsyncSession = Depends(get_db)):
    """
    Завершить цель и выдать награды.
    """
    goal = await _ensure_goal_exists(db, goal_id)
    rewards = await _complete_goal(goal, db)
    await _refresh_goal_with_tasks(db, goal)
    return {
        "goal": GoalResponse.model_validate(goal),
        "rewards": rewards
    }

@app.post("/tasks/generate", response_model=TaskResponse, status_code=201)
async def generate_task(
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """
    Сгенерировать задачу через нейронную сеть.
    Можно использовать только один раз в день.
    """
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверка ограничения "один раз в день"
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    
    result = await db.execute(
        select(TaskGeneration).where(TaskGeneration.user_id == user_id)
    )
    task_gen = result.scalar_one_or_none()
    
    if task_gen:
        last_generated = task_gen.last_generated_at
        if last_generated:
            # Приводим к UTC если нужно
            if last_generated.tzinfo is None:
                last_generated = last_generated.replace(tzinfo=timezone.utc)
            last_generated_date = datetime(
                last_generated.year, 
                last_generated.month, 
                last_generated.day,
                tzinfo=timezone.utc
            )
            if last_generated_date >= today_start:
                raise HTTPException(
                    status_code=429, 
                    detail="Вы уже сгенерировали задачу сегодня. Попробуйте завтра."
                )
        # Обновляем запись
        task_gen.last_generated_at = now
    else:
        # Создаем новую запись
        task_gen = TaskGeneration(user_id=user_id, last_generated_at=now)
        db.add(task_gen)
    
    await db.commit()
    
    # Генерируем задачу через LLM
    generated_task_data = await complexity_evaluator.generate_task()
    is_spam, (reward_coins, reward_intelligence_points, reward_satisfaction) = await _assess_and_reward(
        title=generated_task_data["title"],
        description=generated_task_data.get("description"),
        priority=generated_task_data.get("priority"),
    )
    if is_spam:
        reward_coins = reward_intelligence_points = reward_satisfaction = 0
    
    # Создаем задачу
    task = Task(
        title=generated_task_data["title"],
        description=generated_task_data.get("description"),
        priority=TaskPriority(generated_task_data.get("priority", "medium")),
        reward_coins=reward_coins,
        reward_intelligence_points=reward_intelligence_points,
        reward_satisfaction=reward_satisfaction,
        user_id=user_id
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    return task

@app.get("/tasks/generate/status")
async def get_generate_status(
    user_id: int = Query(..., description="ID пользователя"),
    db: AsyncSession = Depends(get_db)
):
    """
    Проверить, может ли пользователь сгенерировать задачу сегодня
    """
    now = datetime.now(timezone.utc)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    
    result = await db.execute(
        select(TaskGeneration).where(TaskGeneration.user_id == user_id)
    )
    task_gen = result.scalar_one_or_none()
    
    can_generate = True
    last_generated = None
    
    if task_gen and task_gen.last_generated_at:
        last_generated = task_gen.last_generated_at
        if last_generated.tzinfo is None:
            last_generated = last_generated.replace(tzinfo=timezone.utc)
        last_generated_date = datetime(
            last_generated.year,
            last_generated.month,
            last_generated.day,
            tzinfo=timezone.utc
        )
        if last_generated_date >= today_start:
            can_generate = False
    
    return {
        "can_generate": can_generate,
        "last_generated": last_generated.isoformat() if last_generated else None
    }

@app.get("/tasks/", response_model=List[TaskResponse])
async def list_tasks(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Список всех задач"""
    result = await db.execute(select(Task).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Получить задачу по ID"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    return task

@app.get("/tasks/user/{user_id}", response_model=List[TaskResponse])
async def get_user_tasks(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить задачи пользователя"""
    try:
        result = await db.execute(
            select(Task).where(Task.user_id == user_id).offset(skip).limit(limit)
        )
        tasks = result.scalars().all()
        return tasks
    except Exception as e:
        logger.error(f"Ошибка при получении задач пользователя {user_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ошибка при получении задач: {str(e)}")

@app.put("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: int,
    task_in: TaskUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить задачу.
    Если изменяются title, description или priority, стоимость в монетах
    автоматически пересчитывается через нейронную сеть.
    Если задача распознана как спам, награда в монетах сбрасывается в 0.
    """
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    update_data = task_in.model_dump(exclude_unset=True)
    
    # Если изменяются поля, влияющие на сложность, пересчитываем reward_coins
    complexity_fields_changed = any(
        field in update_data for field in ["title", "description", "priority"]
    )
    
    for field, value in update_data.items():
        setattr(task, field, value)
    
    # Пересчитываем стоимость, если изменились поля сложности
    if complexity_fields_changed:
        is_spam, (reward_coins, reward_intelligence_points, reward_satisfaction) = await _assess_and_reward(
            title=task.title,
            description=task.description,
            priority=task.priority,
        )
        if is_spam:
            task.reward_coins = 0
            task.reward_intelligence_points = 0
            task.reward_satisfaction = 0
        else:
            task.reward_coins = reward_coins
            task.reward_intelligence_points = reward_intelligence_points
            task.reward_satisfaction = reward_satisfaction
    
    await db.commit()
    await db.refresh(task)
    return task

@app.delete("/tasks/{task_id}", response_model=TaskResponse)
async def delete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить задачу"""
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    await db.delete(task)
    return task

# Бизнес-логика
@app.post("/tasks/{task_id}/complete")
async def complete_task(task_id: int, db: AsyncSession = Depends(get_db)):
    """
    Завершить задачу и выдать награды через Reward Service
    """
    # Получить задачу
    result = await db.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Задача не найдена")
    
    if task.status == TaskStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Задача уже выполнена")
    
    # Обновить статус
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now()
    await db.commit()
    await db.refresh(task)
    
    # Выдать награды через Reward Service
    reward_service = ServiceClient("reward")
    try:
        rewards = await reward_service.post("/rewards/grant", json={
            "user_id": task.user_id,
            "coins": task.reward_coins,
            "intelligence_points": task.reward_intelligence_points,
            "satisfaction": task.reward_satisfaction,
            "source": "task_completion",
            "source_ref": f"task:{task.id}",
        })
        
        # Проверить достижения после завершения задачи
        achievement_service = ServiceClient("achievement")
        try:
            await achievement_service.post(
                f"/achievements/users/{task.user_id}/check",
                params={"requirement_type": "tasks_completed"}
            )
            logger.info(f"Проверка достижений для пользователя {task.user_id} после завершения задачи {task_id}")
        except Exception as e:
            # Логируем ошибку, но не прерываем выполнение
            logger.error(f"Ошибка при проверке достижений: {str(e)}")
        finally:
            await achievement_service.close()
        
        # Проверить соревнования после завершения задачи
        competition_service = ServiceClient("competition")
        try:
            # Получить все активные соревнования пользователя с метрикой tasks_completed
            # Проверка произойдет автоматически при следующем запросе прогресса
            # Но можно вызвать проверку напрямую через endpoint progress
            await competition_service.get(f"/competitions/check-goal/{task.user_id}")
        except Exception as e:
            # Игнорируем ошибки проверки соревнований
            logger.debug(f"Проверка соревнований не выполнена: {str(e)}")
        finally:
            await competition_service.close()
        
        return {
            "task": TaskResponse.model_validate(task),
            "rewards": rewards
        }
    except Exception as e:
        # Если награды не выданы, откатываем статус
        task.status = TaskStatus.TODO
        task.completed_at = None
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче наград: {str(e)}")
    finally:
        await reward_service.close()

# Фильтрация
@app.get("/tasks/filter/", response_model=List[TaskResponse])
async def filter_tasks(
    user_id: Optional[int] = None,
    status: Optional[TaskStatus] = None,
    priority: Optional[TaskPriority] = None,
    due_before: Optional[datetime] = None,
    due_after: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Фильтрация задач по различным критериям"""
    query = select(Task)
    
    conditions = []
    if user_id:
        conditions.append(Task.user_id == user_id)
    if status:
        conditions.append(Task.status == status)
    if priority:
        conditions.append(Task.priority == priority)
    if due_before:
        conditions.append(Task.due_date <= due_before)
    if due_after:
        conditions.append(Task.due_date >= due_after)
    
    if conditions:
        query = query.where(and_(*conditions))
    
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

# Статистика
@app.get("/tasks/stats/{user_id}")
async def get_task_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика по задачам пользователя"""
    # Получить все задачи пользователя
    result = await db.execute(select(Task).where(Task.user_id == user_id))
    tasks = result.scalars().all()
    
    if not tasks:
        return {
            "user_id": user_id,
            "total": 0,
            "completed": 0,
            "in_progress": 0,
            "todo": 0,
            "cancelled": 0,
            "by_priority": {},
            "completion_rate": 0
        }
    
    stats = {
        "user_id": user_id,
        "total": len(tasks),
        "completed": sum(1 for t in tasks if t.status == TaskStatus.COMPLETED),
        "in_progress": sum(1 for t in tasks if t.status == TaskStatus.IN_PROGRESS),
        "todo": sum(1 for t in tasks if t.status == TaskStatus.TODO),
        "cancelled": sum(1 for t in tasks if t.status == TaskStatus.CANCELLED),
        "by_priority": {
            "low": sum(1 for t in tasks if t.priority == TaskPriority.LOW),
            "medium": sum(1 for t in tasks if t.priority == TaskPriority.MEDIUM),
            "high": sum(1 for t in tasks if t.priority == TaskPriority.HIGH),
            "urgent": sum(1 for t in tasks if t.priority == TaskPriority.URGENT),
        },
        "completion_rate": round(
            sum(1 for t in tasks if t.status == TaskStatus.COMPLETED) / len(tasks) * 100, 2
        ) if tasks else 0
    }
    
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

