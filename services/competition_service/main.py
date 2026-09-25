"""
Competition Service - Управление соревнованиями
Порт: 8010
"""
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, func as sql_func, or_, text
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, validator
import logging

from services.shared.database import get_db, init_db, engine
from services.shared.models.competition import (
    Competition,
    CompetitionParticipant,
    Challenge,
    ChallengeStatus,
    CompetitionDecline,
)
from services.shared.models.user import User
from services.shared.utils import ServiceClient
from services.shared.realtime import push_user_event
from services.competition_service.challenge_ai import ChallengeRewardEvaluator

reward_evaluator = ChallengeRewardEvaluator()
logger = logging.getLogger(__name__)

METRIC_FETCHERS = {
    "tasks_completed": ("task", "/tasks/stats/{user_id}", lambda data: data.get("completed", 0)),
    "habits_completed": ("habit", "/habits/stats/{user_id}", lambda data: data.get("total_completions", 0)),
    "coins_balance": ("user", "/users/{user_id}", lambda data: data.get("coins", 0)),
    "intelligence_points": (
        "character",
        "/characters/user/{user_id}",
        lambda data: (
            data[0].get("intelligence_points", 0)
            if isinstance(data, list) and data
            else data.get("intelligence_points", 0)
        ),
    ),
}


# Pydantic схемы
class CompetitionCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    metric_type: str = Field(..., min_length=1, max_length=50)  # Метрика соревнования
    target_value: Optional[int] = Field(None, ge=0)  # Целевое значение метрики (опционально)
    first_place_coins: int = Field(default=0, ge=0)
    second_place_coins: int = Field(default=0, ge=0)
    third_place_coins: int = Field(default=0, ge=0)
    is_active: bool = True

class CompetitionUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    metric_type: Optional[str] = Field(None, min_length=1, max_length=50)
    target_value: Optional[int] = Field(None, ge=0)
    first_place_coins: Optional[int] = Field(None, ge=0)
    second_place_coins: Optional[int] = Field(None, ge=0)
    third_place_coins: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class CompetitionResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    start_time: datetime
    end_time: datetime
    metric_type: Optional[str]
    target_value: Optional[int]
    first_place_coins: int
    second_place_coins: int
    third_place_coins: int
    is_active: bool
    is_finished: bool
    created_at: datetime
    updated_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class CompetitionParticipantResponse(BaseModel):
    id: int
    competition_id: int
    user_id: int
    score: int
    rank: Optional[int]
    metric_value: Optional[int]
    start_metric_value: Optional[int]
    joined_at: datetime
    completed: bool
    completed_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class ChallengeCreate(BaseModel):
    challenger_id: int = Field(..., ge=1)
    opponent_id: int = Field(..., ge=1)
    metric_type: str = Field(..., min_length=1, max_length=50)
    target_value: int = Field(..., ge=1)
    deadline: datetime

    @validator("deadline")
    def validate_deadline(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("deadline must include timezone information")
        return value


class ChallengeAction(BaseModel):
    user_id: int = Field(..., ge=1)


class ChallengeProgressUpdate(BaseModel):
    user_id: int = Field(..., ge=1)
    increment: int = Field(..., ge=1)


class ChallengeResponse(BaseModel):
    id: int
    challenger_id: int
    opponent_id: int
    metric_type: str
    target_value: int
    reward_coins: int
    reward_intelligence_points: int
    challenger_start_value: int
    opponent_start_value: int
    challenger_progress: int
    opponent_progress: int
    deadline: datetime
    status: ChallengeStatus
    winner_id: Optional[int]
    created_at: datetime
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]
    updated_at: Optional[datetime]
    rewards: Optional[dict] = None

    class Config:
        from_attributes = True


async def ensure_challenge_columns(db: AsyncSession) -> None:
    """Добавляет новые колонки для челленджей при необходимости."""
    alter_statements = [
        "ALTER TABLE challenges ADD COLUMN IF NOT EXISTS deadline TIMESTAMP WITH TIME ZONE",
        "ALTER TABLE challenges ADD COLUMN IF NOT EXISTS challenger_start_value INTEGER DEFAULT 0 NOT NULL",
        "ALTER TABLE challenges ADD COLUMN IF NOT EXISTS opponent_start_value INTEGER DEFAULT 0 NOT NULL",
    ]

    for statement in alter_statements:
        await db.execute(text(statement))
    await db.commit()

    await db.execute(
        text(
            """
            UPDATE challenges
            SET deadline = COALESCE(deadline, created_at + INTERVAL '7 days')
            """
        )
    )
    await db.commit()


async def _fetch_metric_value(user_id: int, metric_type: str) -> int:
    service_info = METRIC_FETCHERS.get(metric_type)
    if not service_info:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип метрики: {metric_type}")

    service_name, endpoint_template, extractor = service_info
    client = ServiceClient(service_name)
    try:
        endpoint = endpoint_template.format(user_id=user_id)
        data = await client.get(endpoint)
        return int(extractor(data) or 0)
    except Exception as exc:
        logger.error("Не удалось получить метрику %s для пользователя %s: %s", metric_type, user_id, exc)
        return 0
    finally:
        await client.close()


async def _distribute_rewards(challenge: Challenge, winner_id: int) -> Optional[dict]:
    if challenge.reward_coins <= 0 and challenge.reward_intelligence_points <= 0:
        return None

    reward_service = ServiceClient("reward")
    try:
        return await reward_service.post(
            "/rewards/grant",
            json={
                "user_id": winner_id,
                "coins": challenge.reward_coins,
                "intelligence_points": challenge.reward_intelligence_points,
            },
        )
    finally:
        await reward_service.close()


async def _synchronize_challenge_progress(db: AsyncSession, challenge: Challenge) -> Optional[dict]:
    """Обновляет прогресс челленджа на основе метрик пользователей."""
    if challenge.status in {ChallengeStatus.CANCELLED, ChallengeStatus.COMPLETED}:
        return None

    changed = False
    rewards_granted = None

    try:
        challenger_value = await _fetch_metric_value(challenge.challenger_id, challenge.metric_type)
    except Exception:
        challenger_value = challenge.challenger_start_value + challenge.challenger_progress

    try:
        opponent_value = await _fetch_metric_value(challenge.opponent_id, challenge.metric_type)
    except Exception:
        opponent_value = challenge.opponent_start_value + challenge.opponent_progress

    if challenge.challenger_start_value == 0 and challenge.challenger_progress == 0:
        challenge.challenger_start_value = challenger_value
        changed = True

    if challenge.opponent_start_value == 0 and challenge.opponent_progress == 0:
        challenge.opponent_start_value = opponent_value
        changed = True

    new_challenger_progress = max(0, challenger_value - challenge.challenger_start_value)
    new_opponent_progress = max(0, opponent_value - challenge.opponent_start_value)

    if new_challenger_progress != challenge.challenger_progress:
        challenge.challenger_progress = new_challenger_progress
        changed = True

    if new_opponent_progress != challenge.opponent_progress:
        challenge.opponent_progress = new_opponent_progress
        changed = True

    now = datetime.now(timezone.utc)

    if challenge.status == ChallengeStatus.PENDING and (
        challenge.challenger_progress > 0 or challenge.opponent_progress > 0
    ):
        challenge.status = ChallengeStatus.ACCEPTED
        challenge.accepted_at = now
        changed = True

    winner_id_to_notify = None
    
    def _complete(winner: int) -> None:
        nonlocal rewards_granted, changed, winner_id_to_notify
        challenge.status = ChallengeStatus.COMPLETED
        challenge.completed_at = now
        challenge.winner_id = winner
        winner_id_to_notify = winner
        changed = True

    if challenge.status in {ChallengeStatus.PENDING, ChallengeStatus.ACCEPTED}:
        if challenge.challenger_progress >= challenge.target_value:
            _complete(challenge.challenger_id)
            rewards_granted = await _distribute_rewards(challenge, challenge.challenger_id)
        elif challenge.opponent_progress >= challenge.target_value:
            _complete(challenge.opponent_id)
            rewards_granted = await _distribute_rewards(challenge, challenge.opponent_id)
        elif challenge.deadline and challenge.deadline < now:
            if challenge.challenger_progress > challenge.opponent_progress:
                _complete(challenge.challenger_id)
                rewards_granted = await _distribute_rewards(challenge, challenge.challenger_id)
            elif challenge.opponent_progress > challenge.challenger_progress:
                _complete(challenge.opponent_id)
                rewards_granted = await _distribute_rewards(challenge, challenge.opponent_id)
            else:
                challenge.status = ChallengeStatus.CANCELLED
                changed = True

    if changed:
        await db.flush()
        await db.refresh(challenge)
        
        # Отправляем уведомления о завершении челленджа, если он был завершен
        if challenge.status == ChallengeStatus.COMPLETED and winner_id_to_notify:
            try:
                bot_service = ServiceClient("max_bot")
                # Получаем имена пользователей
                result = await db.execute(select(User).where(User.id == challenge.challenger_id))
                challenger = result.scalar_one_or_none()
                challenger_name = challenger.username if challenger else None
                
                result = await db.execute(select(User).where(User.id == challenge.opponent_id))
                opponent = result.scalar_one_or_none()
                opponent_name = opponent.username if opponent else None
                
                # Определяем победителя и проигравшего
                winner_name = challenger_name if winner_id_to_notify == challenge.challenger_id else opponent_name
                loser_id = challenge.opponent_id if winner_id_to_notify == challenge.challenger_id else challenge.challenger_id
                loser_name = opponent_name if winner_id_to_notify == challenge.challenger_id else challenger_name
                
                # Отправляем уведомления обоим участникам
                await bot_service.post("/notifications/challenge-completed", json={
                    "winner_user_id": winner_id_to_notify,
                    "loser_user_id": loser_id,
                    "challenge_id": challenge.id,
                    "winner_name": winner_name,
                    "loser_name": loser_name,
                    "reward_coins": challenge.reward_coins
                })
                await bot_service.close()
            except Exception as e:
                logger.warning(f"Не удалось отправить уведомление о завершении челленджа: {e}")

    return rewards_granted

# FastAPI приложение
app = FastAPI(title="Competition Service", version="1.0.0")

async def apply_migration():
    """Применить миграцию для добавления новых колонок в таблицы competitions и competition_participants"""
    from services.shared.database import execute_migration_sql
    
    migration_sql = """
    -- Добавить колонку metric_type в таблицу competitions, если её нет
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='competitions' AND column_name='metric_type') THEN
            ALTER TABLE competitions ADD COLUMN metric_type VARCHAR(50);
        END IF;
    END $$;

    -- Добавить колонку target_value в таблицу competitions, если её нет
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='competitions' AND column_name='target_value') THEN
            ALTER TABLE competitions ADD COLUMN target_value INTEGER;
        END IF;
    END $$;

    -- Добавить колонку metric_value в таблицу competition_participants, если её нет
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='competition_participants' AND column_name='metric_value') THEN
            ALTER TABLE competition_participants ADD COLUMN metric_value INTEGER;
        END IF;
    END $$;

    -- Добавить колонку start_metric_value в таблицу competition_participants, если её нет
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='competition_participants' AND column_name='start_metric_value') THEN
            ALTER TABLE competition_participants ADD COLUMN start_metric_value INTEGER;
        END IF;
    END $$;

    -- Создать таблицу competition_declines, если её нет
    CREATE TABLE IF NOT EXISTS competition_declines (
        id SERIAL PRIMARY KEY,
        competition_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        declined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (competition_id) REFERENCES competitions(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        UNIQUE(competition_id, user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_competition_declines_competition_id ON competition_declines(competition_id);
    CREATE INDEX IF NOT EXISTS idx_competition_declines_user_id ON competition_declines(user_id);
    """
    await execute_migration_sql(migration_sql)

from services.competition_service.minigame import router as minigame_router  # noqa: E402

app.include_router(minigame_router)


@app.on_event("startup")
async def startup():
    await init_db()
    # Применить миграцию для добавления новых колонок
    await apply_migration()
    async for session in get_db():
        await ensure_challenge_columns(session)
        await session.close()
        break

@app.get("/")
async def root():
    return {"service": "Competition Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD соревнований
@app.post("/competitions/", response_model=CompetitionResponse, status_code=201)
async def create_competition(
    competition_in: CompetitionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать соревнование"""
    if competition_in.end_time <= competition_in.start_time:
        raise HTTPException(status_code=400, detail="Время окончания должно быть позже времени начала")
    
    # Валидация метрики
    if competition_in.metric_type not in METRIC_FETCHERS:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип метрики: {competition_in.metric_type}. Доступные: {', '.join(METRIC_FETCHERS.keys())}")
    
    competition = Competition(**competition_in.model_dump())
    db.add(competition)
    await db.commit()
    await db.refresh(competition)
    
    # Отправляем уведомления всем пользователям о создании соревнования
    try:
        # Получаем всех пользователей
        user_service = ServiceClient("user")
        users_response = await user_service.get("/users/", params={"limit": 10000})
        await user_service.close()
        
        if isinstance(users_response, list):
            user_ids = [user.get("id") for user in users_response if user.get("id")]
            
            if user_ids:
                bot_service = ServiceClient("max_bot")
                from datetime import datetime
                start_time_str = competition.start_time.strftime("%d.%m.%Y %H:%M") if competition.start_time else None
                end_time_str = competition.end_time.strftime("%d.%m.%Y %H:%M") if competition.end_time else None
                
                await bot_service.post("/notifications/competition-created", json={
                    "user_ids": user_ids,
                    "competition_name": competition.name,
                    "competition_id": competition.id,
                    "description": competition.description,
                    "start_time": start_time_str,
                    "end_time": end_time_str
                })
                await bot_service.close()

                # Отправляем realtime-события пользователям
                for user_id in user_ids:
                    await push_user_event(
                        user_id,
                        "competitions.competition.announced",
                        payload={
                            "competition_id": competition.id,
                            "competition_name": competition.name,
                            "description": competition.description,
                            "start_time": start_time_str,
                            "end_time": end_time_str,
                        },
                        metadata={"source": "competition_service"},
                    )
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомления о создании соревнования: {e}")
    
    return competition

@app.get("/competitions/", response_model=List[CompetitionResponse])
async def list_competitions(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = False,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Список всех соревнований"""
    query = select(Competition)
    
    if active_only:
        query = query.where(and_(
            Competition.is_active == True,
            Competition.is_finished == False
        ))
    
    # Исключить соревнования, от которых пользователь отказался
    if user_id:
        declined_competition_ids = select(CompetitionDecline.competition_id).where(
            CompetitionDecline.user_id == user_id
        )
        query = query.where(~Competition.id.in_(declined_competition_ids))
    
    query = query.order_by(Competition.start_time.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()


# ===== Персональные челленджи =====
async def _ensure_user_exists(db: AsyncSession, user_id: int) -> User:
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail=f"Пользователь {user_id} не найден")
    return user


@app.post("/challenges/", response_model=ChallengeResponse, status_code=201)
async def create_challenge(
    challenge_in: ChallengeCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать персональный челлендж между двумя пользователями"""
    if challenge_in.challenger_id == challenge_in.opponent_id:
        raise HTTPException(status_code=400, detail="Нельзя бросить вызов самому себе")

    now = datetime.now(timezone.utc)
    deadline = challenge_in.deadline.astimezone(timezone.utc)
    if deadline <= now:
        raise HTTPException(status_code=400, detail="Дедлайн должен быть в будущем")

    # Проверить существование пользователей
    challenger = await _ensure_user_exists(db, challenge_in.challenger_id)
    opponent = await _ensure_user_exists(db, challenge_in.opponent_id)

    # Проверить активные челленджи между пользователями в обе стороны
    result = await db.execute(
        select(Challenge).where(
            and_(
                Challenge.status.in_([ChallengeStatus.PENDING, ChallengeStatus.ACCEPTED]),
                or_(
                    and_(
                        Challenge.challenger_id == challenge_in.challenger_id,
                        Challenge.opponent_id == challenge_in.opponent_id,
                    ),
                    and_(
                        Challenge.challenger_id == challenge_in.opponent_id,
                        Challenge.opponent_id == challenge_in.challenger_id,
                    ),
                ),
            )
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Активный челлендж между пользователями уже существует")

    try:
        challenger_current = await _fetch_metric_value(challenge_in.challenger_id, challenge_in.metric_type)
        opponent_current = await _fetch_metric_value(challenge_in.opponent_id, challenge_in.metric_type)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось получить метрику: {exc}") from exc

    # Рассчитываем награды через LLM
    challenger_name = getattr(challenger, "username", str(challenger.id))
    opponent_name = getattr(opponent, "username", str(opponent.id))
    try:
        reward_coins, reward_intelligence = await reward_evaluator.evaluate_rewards(
            metric_type=challenge_in.metric_type,
            target_value=challenge_in.target_value,
            deadline_iso=deadline.isoformat(),
            challenger_name=challenger_name,
            opponent_name=opponent_name,
        )
    except Exception as exc:
        logger.error("Не удалось вычислить награду через LLM: %s", exc)
        reward_coins, reward_intelligence = 10, 5

    challenge = Challenge(
        challenger_id=challenge_in.challenger_id,
        opponent_id=challenge_in.opponent_id,
        metric_type=challenge_in.metric_type,
        target_value=challenge_in.target_value,
        reward_coins=reward_coins,
        reward_intelligence_points=reward_intelligence,
        deadline=deadline,
        challenger_start_value=challenger_current,
        opponent_start_value=opponent_current,
        status=ChallengeStatus.PENDING,
    )
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)

    rewards = await _synchronize_challenge_progress(db, challenge)
    await db.commit()
    
    # Отправляем уведомление оппоненту о создании челленджа
    try:
        bot_service = ServiceClient("max_bot")
        deadline_str = challenge.deadline.strftime("%d.%m.%Y %H:%M") if challenge.deadline else None
        metric_labels = {
            "tasks_completed": "Выполненных задач",
            "habits_completed": "Записей в дневнике",
            "coins_balance": "Монет",
            "intelligence_points": "Очков интеллекта"
        }
        metric_label = metric_labels.get(challenge.metric_type, challenge.metric_type)
        
        await bot_service.post("/notifications/challenge-request", json={
            "recipient_user_id": challenge.opponent_id,
            "initiator_user_id": challenge.challenger_id,
            "challenge_id": challenge.id,
            "initiator_username": challenger_name,
            "metric_type": metric_label,
            "target_value": challenge.target_value,
            "deadline": deadline_str,
            "reward_coins": challenge.reward_coins
        })
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о создании челленджа: {e}")

    # realtime-событие оппоненту
    try:
        await push_user_event(
            challenge.opponent_id,
            "competitions.challenge.invited",
            payload={
                "challenge_id": challenge.id,
                "challenger_id": challenge.challenger_id,
                "challenger_username": challenger_name,
                "metric_type": challenge.metric_type,
                "target_value": challenge.target_value,
                "deadline": challenge.deadline.isoformat() if challenge.deadline else None,
                "reward_coins": challenge.reward_coins,
                "reward_intelligence_points": challenge.reward_intelligence_points,
            },
            metadata={"source": "competition_service"},
        )
    except Exception as exc:
        logger.warning("Не удалось отправить realtime-событие для челленджа: %s", exc)
    
    base_response = ChallengeResponse.model_validate(challenge)
    if rewards:
        return base_response.model_copy(update={"rewards": rewards})
    return base_response


@app.post("/challenges/{challenge_id}/accept", response_model=ChallengeResponse)
async def accept_challenge(
    challenge_id: int,
    payload: ChallengeAction,
    db: AsyncSession = Depends(get_db)
):
    """Принять челлендж"""
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    if challenge.status != ChallengeStatus.PENDING:
        raise HTTPException(status_code=400, detail="Челлендж нельзя принять в текущем статусе")

    if payload.user_id != challenge.opponent_id:
        raise HTTPException(status_code=403, detail="Принять челлендж может только приглашенный игрок")

    challenge.status = ChallengeStatus.ACCEPTED
    challenge.accepted_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(challenge)
    
    # Отправляем уведомление инициатору о принятии челленджа
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == payload.user_id))
        acceptor = result.scalar_one_or_none()
        acceptor_username = acceptor.username if acceptor else None
        await bot_service.post("/notifications/challenge-accepted", json={
            "initiator_user_id": challenge.challenger_id,
            "acceptor_username": acceptor_username
        })
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о принятии челленджа: {e}")

    return ChallengeResponse.model_validate(challenge)


@app.post("/challenges/{challenge_id}/decline", response_model=ChallengeResponse)
async def decline_challenge(
    challenge_id: int,
    payload: ChallengeAction,
    db: AsyncSession = Depends(get_db)
):
    """Отклонить челлендж"""
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    if challenge.status != ChallengeStatus.PENDING:
        raise HTTPException(status_code=400, detail="Челлендж нельзя отклонить в текущем статусе")

    if payload.user_id not in {challenge.opponent_id, challenge.challenger_id}:
        raise HTTPException(status_code=403, detail="Игрок не участвует в челлендже")

    challenge.status = ChallengeStatus.DECLINED
    await db.commit()
    await db.refresh(challenge)
    
    # Отправляем уведомление инициатору об отклонении челленджа
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == payload.user_id))
        rejector = result.scalar_one_or_none()
        rejector_username = rejector.username if rejector else None
        await bot_service.post("/notifications/challenge-rejected", json={
            "initiator_user_id": challenge.challenger_id,
            "rejector_username": rejector_username
        })
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление об отклонении челленджа: {e}")

    return ChallengeResponse.model_validate(challenge)


@app.post("/challenges/{challenge_id}/cancel", response_model=ChallengeResponse)
async def cancel_challenge(
    challenge_id: int,
    payload: ChallengeAction,
    db: AsyncSession = Depends(get_db)
):
    """Отменить челлендж до его принятия"""
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    if challenge.status not in {ChallengeStatus.PENDING, ChallengeStatus.ACCEPTED}:
        raise HTTPException(status_code=400, detail="Челлендж нельзя отменить в текущем статусе")

    if payload.user_id != challenge.challenger_id:
        raise HTTPException(status_code=403, detail="Отменить челлендж может только инициатор")

    challenge.status = ChallengeStatus.CANCELLED
    await db.commit()
    await db.refresh(challenge)

    return ChallengeResponse.model_validate(challenge)


@app.post("/challenges/{challenge_id}/progress", response_model=ChallengeResponse)
async def update_challenge_progress(
    challenge_id: int,
    payload: ChallengeProgressUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить прогресс челленджа для игрока"""
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")

    if challenge.status not in {ChallengeStatus.ACCEPTED, ChallengeStatus.PENDING}:
        raise HTTPException(status_code=400, detail="Прогресс нельзя обновить в текущем статусе")

    if payload.user_id not in {challenge.challenger_id, challenge.opponent_id}:
        raise HTTPException(status_code=403, detail="Игрок не участвует в челлендже")

    if challenge.status == ChallengeStatus.PENDING and payload.user_id == challenge.opponent_id:
        # Автоматически принимаем челлендж при первом обновлении прогресса приглашенным игроком
        challenge.status = ChallengeStatus.ACCEPTED
        challenge.accepted_at = datetime.now(timezone.utc)

    if payload.user_id == challenge.challenger_id:
        challenge.challenger_progress += payload.increment
        current_progress = challenge.challenger_progress
    else:
        challenge.opponent_progress += payload.increment
        current_progress = challenge.opponent_progress

    # Проверка на победу
    rewards_granted = None
    challenge_completed = False
    if current_progress >= challenge.target_value and challenge.status != ChallengeStatus.COMPLETED:
        challenge.status = ChallengeStatus.COMPLETED
        challenge.completed_at = datetime.now(timezone.utc)
        challenge.winner_id = payload.user_id
        challenge_completed = True

        if challenge.reward_coins > 0 or challenge.reward_intelligence_points > 0:
            reward_service = ServiceClient("reward")
            try:
                rewards_granted = await reward_service.post("/rewards/grant", json={
                    "user_id": payload.user_id,
                    "coins": challenge.reward_coins,
                    "intelligence_points": challenge.reward_intelligence_points
                })
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка при выдаче награды: {str(e)}")
            finally:
                await reward_service.close()

    await db.commit()
    await db.refresh(challenge)
    
    # Отправляем уведомления о завершении челленджа
    if challenge_completed:
        try:
            bot_service = ServiceClient("max_bot")
            # Получаем имена пользователей
            result = await db.execute(select(User).where(User.id == challenge.challenger_id))
            challenger = result.scalar_one_or_none()
            challenger_name = challenger.username if challenger else None
            
            result = await db.execute(select(User).where(User.id == challenge.opponent_id))
            opponent = result.scalar_one_or_none()
            opponent_name = opponent.username if opponent else None
            
            # Отправляем уведомление победителю
            winner_name = challenger_name if payload.user_id == challenge.challenger_id else opponent_name
            loser_id = challenge.opponent_id if payload.user_id == challenge.challenger_id else challenge.challenger_id
            loser_name = opponent_name if payload.user_id == challenge.challenger_id else challenger_name
            
            await bot_service.post("/notifications/challenge-completed", json={
                "winner_user_id": payload.user_id,
                "loser_user_id": loser_id,
                "challenge_id": challenge.id,
                "winner_name": winner_name,
                "loser_name": loser_name,
                "reward_coins": challenge.reward_coins
            })
            await bot_service.close()
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о завершении челленджа: {e}")

    base_response = ChallengeResponse.model_validate(challenge)
    if rewards_granted:
        return base_response.model_copy(update={"rewards": rewards_granted})
    return base_response


@app.get("/challenges/{challenge_id}", response_model=ChallengeResponse)
async def get_challenge(challenge_id: int, db: AsyncSession = Depends(get_db)):
    """Получить информацию о челлендже"""
    result = await db.execute(select(Challenge).where(Challenge.id == challenge_id))
    challenge = result.scalar_one_or_none()
    if not challenge:
        raise HTTPException(status_code=404, detail="Челлендж не найден")
    rewards = await _synchronize_challenge_progress(db, challenge)
    await db.commit()
    base_response = ChallengeResponse.model_validate(challenge)
    if rewards:
        return base_response.model_copy(update={"rewards": rewards})
    return base_response


@app.get("/challenges/users/{user_id}", response_model=List[ChallengeResponse])
async def list_user_challenges(
    user_id: int,
    status: Optional[ChallengeStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить все челленджи пользователя"""
    await _ensure_user_exists(db, user_id)

    query = select(Challenge).where(
        or_(
            Challenge.challenger_id == user_id,
            Challenge.opponent_id == user_id
        )
    )

    if status:
        query = query.where(Challenge.status == status)

    result = await db.execute(query.order_by(Challenge.created_at.desc()))
    challenges = result.scalars().all()

    responses: List[ChallengeResponse] = []
    rewards_to_include: List[Optional[dict]] = []
    for challenge in challenges:
        rewards = await _synchronize_challenge_progress(db, challenge)
        responses.append(ChallengeResponse.model_validate(challenge))
        rewards_to_include.append(rewards)

    await db.commit()

    final_responses: List[ChallengeResponse] = []
    for base, rewards in zip(responses, rewards_to_include):
        if rewards:
            final_responses.append(base.model_copy(update={"rewards": rewards}))
        else:
            final_responses.append(base)
    return final_responses

@app.get("/competitions/{competition_id}", response_model=CompetitionResponse)
async def get_competition(competition_id: int, db: AsyncSession = Depends(get_db)):
    """Получить соревнование по ID"""
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    return competition

@app.put("/competitions/{competition_id}", response_model=CompetitionResponse)
async def update_competition(
    competition_id: int,
    competition_in: CompetitionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить соревнование"""
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    
    update_data = competition_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(competition, field, value)
    
    await db.commit()
    await db.refresh(competition)
    return competition

@app.delete("/competitions/{competition_id}", response_model=CompetitionResponse)
async def delete_competition(competition_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить соревнование"""
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    
    await db.delete(competition)
    return competition

# Участие в соревнованиях
@app.post("/competitions/{competition_id}/join")
async def join_competition(
    competition_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Присоединиться к соревнованию"""
    # Проверка соревнования
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    
    if not competition.is_active:
        raise HTTPException(status_code=400, detail="Соревнование неактивно")
    
    if competition.is_finished:
        raise HTTPException(status_code=400, detail="Соревнование завершено")
    
    # Проверка пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверить, не участвует ли уже
    result = await db.execute(
        select(CompetitionParticipant).where(and_(
            CompetitionParticipant.competition_id == competition_id,
            CompetitionParticipant.user_id == user_id
        ))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь уже участвует в соревновании")
    
    # Удалить отказ, если пользователь ранее отказался
    result = await db.execute(
        select(CompetitionDecline).where(and_(
            CompetitionDecline.competition_id == competition_id,
            CompetitionDecline.user_id == user_id
        ))
    )
    decline = result.scalar_one_or_none()
    if decline:
        await db.delete(decline)
    
    # Получить начальное значение метрики при присоединении
    start_metric_value = None
    if competition.metric_type:
        try:
            start_metric_value = await _fetch_metric_value(user_id, competition.metric_type)
        except Exception as e:
            logger.warning(f"Не удалось получить начальное значение метрики при присоединении: {e}")
    
    participant = CompetitionParticipant(
        competition_id=competition_id, 
        user_id=user_id,
        start_metric_value=start_metric_value
    )
    db.add(participant)
    await db.commit()
    await db.refresh(participant)
    
    # Проверить, достиг ли пользователь цели сразу после присоединения
    # Учитываем только прогресс после присоединения (0, так как только что присоединились)
    if competition.target_value and competition.metric_type:
        try:
            # Прогресс = текущее значение - начальное значение
            # При присоединении прогресс = 0, поэтому проверяем, что цель > 0
            if competition.target_value > 0:
                # Не завершаем сразу, так как прогресс = 0
                pass
        except Exception as e:
            logger.warning(f"Не удалось проверить достижение цели при присоединении: {e}")
    
    return CompetitionParticipantResponse.model_validate(participant)

@app.post("/competitions/{competition_id}/decline")
async def decline_competition(
    competition_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отказаться от участия в соревновании"""
    # Проверка соревнования
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    
    # Проверка пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверить, не отказался ли уже
    result = await db.execute(
        select(CompetitionDecline).where(and_(
            CompetitionDecline.competition_id == competition_id,
            CompetitionDecline.user_id == user_id
        ))
    )
    if result.scalar_one_or_none():
        return {"message": "Вы уже отказались от этого соревнования"}
    
    # Удалить участие, если пользователь был участником
    result = await db.execute(
        select(CompetitionParticipant).where(and_(
            CompetitionParticipant.competition_id == competition_id,
            CompetitionParticipant.user_id == user_id
        ))
    )
    participant = result.scalar_one_or_none()
    if participant:
        await db.delete(participant)
    
    # Создать запись об отказе
    decline = CompetitionDecline(competition_id=competition_id, user_id=user_id)
    db.add(decline)
    await db.commit()
    
    return {"message": "Вы отказались от участия в соревновании"}

@app.get("/competitions/{competition_id}/participants/{user_id}")
async def get_user_participation(
    competition_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию об участии пользователя в соревновании"""
    result = await db.execute(
        select(CompetitionParticipant).where(and_(
            CompetitionParticipant.competition_id == competition_id,
            CompetitionParticipant.user_id == user_id
        ))
    )
    participant = result.scalar_one_or_none()
    if participant:
        return CompetitionParticipantResponse.model_validate(participant)
    # Возвращаем 404 вместо None, чтобы фронтенд правильно обрабатывал отсутствие участия
    raise HTTPException(status_code=404, detail="Пользователь не участвует в этом соревновании")

async def _check_and_finalize_competitions_for_user(user_id: int, db: AsyncSession):
    """
    Проверить все активные соревнования пользователя и завершить те, где достигнута цель
    """
    try:
        # Получить все активные соревнования, где пользователь участвует
        result = await db.execute(
            select(Competition, CompetitionParticipant)
            .join(CompetitionParticipant, CompetitionParticipant.competition_id == Competition.id)
            .where(and_(
                CompetitionParticipant.user_id == user_id,
                Competition.is_active == True,
                Competition.is_finished == False,
                Competition.target_value.isnot(None),
                Competition.metric_type.isnot(None)
            ))
        )
        competitions_with_participants = result.all()
        
        for competition, participant in competitions_with_participants:
            try:
                current_value = await _fetch_metric_value(user_id, competition.metric_type)
                # Учитываем только прогресс после присоединения
                start_value = participant.start_metric_value if participant.start_metric_value is not None else 0
                progress_value = max(0, current_value - start_value)
                if progress_value >= competition.target_value:
                    # Автоматически завершить соревнование
                    await _auto_finalize_competition(competition.id, db)
            except Exception as e:
                logger.warning(f"Ошибка проверки соревнования {competition.id} для пользователя {user_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка проверки соревнований для пользователя {user_id}: {e}")

@app.get("/competitions/check-goal/{user_id}")
async def check_competition_goals(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    Проверить все активные соревнования пользователя и завершить те, где достигнута цель
    Вызывается после выполнения задач/привычек
    """
    await _check_and_finalize_competitions_for_user(user_id, db)
    return {"message": "Проверка завершена"}

@app.get("/competitions/{competition_id}/progress/{user_id}")
async def get_user_competition_progress(
    competition_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить текущий прогресс пользователя в соревновании"""
    # Проверка соревнования
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    
    if not competition.metric_type:
        raise HTTPException(status_code=400, detail="У соревнования не указана метрика")
    
    # Получить информацию об участии пользователя
    participant_result = await db.execute(
        select(CompetitionParticipant).where(and_(
            CompetitionParticipant.competition_id == competition_id,
            CompetitionParticipant.user_id == user_id
        ))
    )
    participant = participant_result.scalar_one_or_none()
    
    # Получить текущее значение метрики
    try:
        current_value = await _fetch_metric_value(user_id, competition.metric_type)
    except Exception as e:
        logger.error(f"Ошибка получения метрики для пользователя {user_id}: {e}")
        current_value = 0
    
    # Учитываем только прогресс после присоединения
    start_value = participant.start_metric_value if participant and participant.start_metric_value is not None else 0
    progress_value = max(0, current_value - start_value)
    
    # Вычислить оставшееся до цели
    remaining = None
    if competition.target_value:
        remaining = max(0, competition.target_value - progress_value)
        
        # Проверить, достиг ли пользователь цели и завершить соревнование автоматически
        if not competition.is_finished and progress_value >= competition.target_value:
            if participant:
                # Автоматически завершить соревнование
                await _auto_finalize_competition(competition_id, db)
                # Обновить competition после финализации
                result = await db.execute(select(Competition).where(Competition.id == competition_id))
                competition = result.scalar_one_or_none()
    
    return {
        "current_value": progress_value,  # Возвращаем только прогресс
        "target_value": competition.target_value,
        "remaining": remaining,
        "metric_type": competition.metric_type
    }

class UpdateScoreRequest(BaseModel):
    score: int = Field(..., ge=0)

@app.post("/competitions/{competition_id}/participants/{user_id}/score")
async def update_participant_score(
    competition_id: int,
    user_id: int,
    request: UpdateScoreRequest,
    db: AsyncSession = Depends(get_db)
):
    """Обновить счет участника"""
    result = await db.execute(
        select(CompetitionParticipant).where(and_(
            CompetitionParticipant.competition_id == competition_id,
            CompetitionParticipant.user_id == user_id
        ))
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")
    
    participant.score = request.score
    await db.commit()
    await db.refresh(participant)
    
    return CompetitionParticipantResponse.model_validate(participant)

@app.post("/competitions/{competition_id}/complete/{user_id}")
async def complete_competition(
    competition_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Завершить соревнование для участника"""
    result = await db.execute(
        select(CompetitionParticipant).where(and_(
            CompetitionParticipant.competition_id == competition_id,
            CompetitionParticipant.user_id == user_id
        ))
    )
    participant = result.scalar_one_or_none()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Участник не найден")
    
    if participant.completed:
        raise HTTPException(status_code=400, detail="Соревнование уже завершено для этого участника")
    
    participant.completed = True
    participant.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(participant)
    
    return CompetitionParticipantResponse.model_validate(participant)

async def _auto_finalize_competition(competition_id: int, db: AsyncSession):
    """
    Автоматически завершить соревнование при достижении цели
    Вызывается когда участник достигает target_value
    """
    try:
        # Получить соревнование
        result = await db.execute(select(Competition).where(Competition.id == competition_id))
        competition = result.scalar_one_or_none()
        if not competition or competition.is_finished:
            return
        
        if not competition.metric_type:
            return
        
        # Получить всех участников
        result = await db.execute(
            select(CompetitionParticipant)
            .where(CompetitionParticipant.competition_id == competition_id)
        )
        participants = result.scalars().all()
        
        if not participants:
            return
        
        # Собрать значения метрик для всех участников (учитываем только прогресс после присоединения)
        for participant in participants:
            try:
                current_value = await _fetch_metric_value(participant.user_id, competition.metric_type)
                # Учитываем только прогресс после присоединения
                start_value = participant.start_metric_value if participant.start_metric_value is not None else 0
                progress_value = max(0, current_value - start_value)
                participant.metric_value = progress_value
                if participant.score == 0:
                    participant.score = progress_value
            except Exception as e:
                logger.warning(f"Не удалось получить метрику {competition.metric_type} для пользователя {participant.user_id}: {e}")
                if participant.metric_value is None:
                    participant.metric_value = participant.score
        
        # Отсортировать участников по значению метрики (прогрессу)
        participants.sort(key=lambda p: p.metric_value if p.metric_value is not None else p.score, reverse=True)
        
        # Присвоить места
        for rank, participant in enumerate(participants, start=1):
            participant.rank = rank
            if participant.metric_value is not None:
                participant.score = participant.metric_value
        
        await db.commit()
        
        # Выдать награды топ-3
        reward_service = ServiceClient("reward")
        
        try:
            # Первое место
            if len(participants) >= 1 and competition.first_place_coins > 0:
                first = participants[0]
                await reward_service.post("/rewards/grant", json={
                    "user_id": first.user_id,
                    "coins": competition.first_place_coins,
                    "intelligence_points": 0
                })
            
            # Второе место
            if len(participants) >= 2 and competition.second_place_coins > 0:
                second = participants[1]
                await reward_service.post("/rewards/grant", json={
                    "user_id": second.user_id,
                    "coins": competition.second_place_coins,
                    "intelligence_points": 0
                })
            
            # Третье место
            if len(participants) >= 3 and competition.third_place_coins > 0:
                third = participants[2]
                await reward_service.post("/rewards/grant", json={
                    "user_id": third.user_id,
                    "coins": competition.third_place_coins,
                    "intelligence_points": 0
                })
            
            await reward_service.close()
        except Exception as e:
            logger.error(f"Ошибка выдачи наград при автоматическом завершении соревнования: {e}")
            await reward_service.close()
        
        # Отметить соревнование как завершенное
        competition.is_finished = True
        await db.commit()
        
        # Отправить уведомления участникам
        try:
            bot_service = ServiceClient("max_bot")
            for participant in participants[:3]:  # Только топ-3
                rank = participant.rank
                reward_coins = 0
                if rank == 1:
                    reward_coins = competition.first_place_coins
                elif rank == 2:
                    reward_coins = competition.second_place_coins
                elif rank == 3:
                    reward_coins = competition.third_place_coins
                
                await bot_service.post("/notifications/competition-finished", json={
                    "user_id": participant.user_id,
                    "competition_name": competition.name,
                    "rank": rank,
                    "reward_coins": reward_coins
                })
            await bot_service.close()
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомления о завершении соревнования: {e}")
        
        logger.info(f"Соревнование {competition_id} автоматически завершено")
    except Exception as e:
        logger.error(f"Ошибка автоматического завершения соревнования {competition_id}: {e}", exc_info=True)

@app.post("/competitions/{competition_id}/finalize")
async def finalize_competition(competition_id: int, db: AsyncSession = Depends(get_db)):
    """
    Завершить соревнование и выдать награды
    1. Собрать значения метрик для всех участников
    2. Рассчитать рейтинг участников
    3. Выдать награды через Reward Service
    4. Отметить соревнование как завершенное
    """
    # Получить соревнование
    result = await db.execute(select(Competition).where(Competition.id == competition_id))
    competition = result.scalar_one_or_none()
    if not competition:
        raise HTTPException(status_code=404, detail="Соревнование не найдено")
    
    if competition.is_finished:
        raise HTTPException(status_code=400, detail="Соревнование уже завершено")
    
    if not competition.metric_type:
        raise HTTPException(status_code=400, detail="У соревнования не указана метрика")
    
    # Получить всех участников
    result = await db.execute(
        select(CompetitionParticipant)
        .where(CompetitionParticipant.competition_id == competition_id)
    )
    participants = result.scalars().all()
    
    if not participants:
        raise HTTPException(status_code=400, detail="Нет участников в соревновании")
    
    # Собрать значения метрик для всех участников (учитываем только прогресс после присоединения)
    for participant in participants:
        try:
            current_value = await _fetch_metric_value(participant.user_id, competition.metric_type)
            # Учитываем только прогресс после присоединения
            start_value = participant.start_metric_value if participant.start_metric_value is not None else 0
            progress_value = max(0, current_value - start_value)
            participant.metric_value = progress_value
            # Обновить score на основе метрики (если не был установлен вручную)
            if participant.score == 0:
                participant.score = progress_value
        except Exception as e:
            logger.warning(f"Не удалось получить метрику {competition.metric_type} для пользователя {participant.user_id}: {e}")
            # Если не удалось получить метрику, используем текущий score
            if participant.metric_value is None:
                participant.metric_value = participant.score
    
    # Отсортировать участников по значению метрики (прогрессу)
    participants.sort(key=lambda p: p.metric_value if p.metric_value is not None else p.score, reverse=True)
    
    # Присвоить места и обновить score на основе метрики
    for rank, participant in enumerate(participants, start=1):
        participant.rank = rank
        # Обновить score на основе метрики, если она была получена
        if participant.metric_value is not None:
            participant.score = participant.metric_value
    
    await db.commit()
    
    # Выдать награды топ-3 через Reward Service
    reward_service = ServiceClient("reward")
    rewards_info = []
    
    try:
        # Первое место
        if len(participants) >= 1 and competition.first_place_coins > 0:
            first = participants[0]
            rewards = await reward_service.post("/rewards/grant", json={
                "user_id": first.user_id,
                "coins": competition.first_place_coins,
                "intelligence_points": 0
            })
            rewards_info.append({
                "user_id": first.user_id,
                "rank": 1,
                "coins": competition.first_place_coins,
                "rewards": rewards
            })
        
        # Второе место
        if len(participants) >= 2 and competition.second_place_coins > 0:
            second = participants[1]
            rewards = await reward_service.post("/rewards/grant", json={
                "user_id": second.user_id,
                "coins": competition.second_place_coins,
                "intelligence_points": 0
            })
            rewards_info.append({
                "user_id": second.user_id,
                "rank": 2,
                "coins": competition.second_place_coins,
                "rewards": rewards
            })
        
        # Третье место
        if len(participants) >= 3 and competition.third_place_coins > 0:
            third = participants[2]
            rewards = await reward_service.post("/rewards/grant", json={
                "user_id": third.user_id,
                "coins": competition.third_place_coins,
                "intelligence_points": 0
            })
            rewards_info.append({
                "user_id": third.user_id,
                "rank": 3,
                "coins": competition.third_place_coins,
                "rewards": rewards
            })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче наград: {str(e)}")
    finally:
        await reward_service.close()
    
    # Отметить соревнование как завершенное
    competition.is_finished = True
    await db.commit()
    
    # Отправляем уведомления участникам о завершении соревнования
    try:
        bot_service = ServiceClient("max_bot")
        for participant in participants:
            rank = participant.rank
            reward_coins = 0
            if rank == 1:
                reward_coins = competition.first_place_coins
            elif rank == 2:
                reward_coins = competition.second_place_coins
            elif rank == 3:
                reward_coins = competition.third_place_coins
            
            await bot_service.post("/notifications/competition-finished", json={
                "user_id": participant.user_id,
                "competition_name": competition.name,
                "rank": rank,
                "reward_coins": reward_coins
            })
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомления о завершении соревнования: {e}")
    
    return {
        "competition_id": competition_id,
        "total_participants": len(participants),
        "rewards_distributed": rewards_info
    }

@app.get("/competitions/{competition_id}/leaderboard")
async def get_competition_leaderboard(
    competition_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить таблицу лидеров соревнования"""
    result = await db.execute(
        select(CompetitionParticipant)
        .where(CompetitionParticipant.competition_id == competition_id)
        .order_by(CompetitionParticipant.score.desc())
        .offset(skip)
        .limit(limit)
    )
    participants = result.scalars().all()
    
    return [CompetitionParticipantResponse.model_validate(p) for p in participants]

@app.get("/competitions/users/{user_id}")
async def get_user_competitions(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить соревнования пользователя"""
    result = await db.execute(
        select(CompetitionParticipant)
        .where(CompetitionParticipant.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

@app.get("/competitions/stats/{user_id}")
async def get_user_competition_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика по соревнованиям пользователя"""
    result = await db.execute(
        select(CompetitionParticipant).where(CompetitionParticipant.user_id == user_id)
    )
    participations = result.scalars().all()
    
    total = len(participations)
    completed = sum(1 for p in participations if p.completed)
    
    # Подсчитать призовые места
    first_places = sum(1 for p in participations if p.rank == 1)
    second_places = sum(1 for p in participations if p.rank == 2)
    third_places = sum(1 for p in participations if p.rank == 3)
    
    return {
        "user_id": user_id,
        "total_competitions": total,
        "completed_competitions": completed,
        "first_places": first_places,
        "second_places": second_places,
        "third_places": third_places
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8010)

