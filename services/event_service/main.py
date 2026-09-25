"""
Event Service - Управление событиями и посещаемостью
Порт: 8008
"""
import asyncio
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, and_, or_, func as sql_func
from typing import List, Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator

from services.shared.database import get_db, init_db, engine
from sqlalchemy import text
from services.shared.models.event import Event, EventAttendance, event_groups
from services.shared.models.lesson import Lesson, LessonAttendance, VerificationMethod, lesson_groups
from services.shared.models.social import StudentGroup, GroupMember
from services.shared.models.user import User
from services.shared.utils import ServiceClient
from services.shared.auth import require_admin
from services.shared.migrations import apply_hackathon_migrations
from services.shared.timeutil import local_to_utc
from services.shared import attendance_codes
from services.event_service import lesson_checkin, streak_service, schedule_import, engagement
import qrcode
import io
import json
import secrets
import random
import hashlib
import logging
from sqlalchemy import insert, delete

# Pydantic схемы
class StudentGroupBasic(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class EventCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    start_time: datetime
    end_time: Optional[datetime] = None
    max_participants: Optional[int] = Field(None, ge=1)
    is_public: bool = True
    reward_coins: int = Field(default=0, ge=0)
    reward_intelligence_points: int = Field(default=0, ge=0)
    group_ids: Optional[List[int]] = Field(default=None, description="Список ID групп для события")

class EventUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    max_participants: Optional[int] = Field(None, ge=1)
    is_public: Optional[bool] = None
    reward_coins: Optional[int] = Field(None, ge=0)
    reward_intelligence_points: Optional[int] = Field(None, ge=0)
    group_ids: Optional[List[int]] = Field(None, description="Список ID групп для события")

class EventResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    location: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    max_participants: Optional[int]
    is_public: bool
    reward_coins: int
    reward_intelligence_points: int
    qr_token: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime]
    groups: List[StudentGroupBasic] = []

    @field_validator("qr_token", mode="before")
    @classmethod
    def _hide_code(cls, value):
        # Текущий код события виден только администратору через /events/{id}/code
        return None

    class Config:
        from_attributes = True

class EventAttendanceResponse(BaseModel):
    id: int
    event_id: int
    user_id: int
    registered_at: datetime
    attended: bool
    attended_at: Optional[datetime]
    
    class Config:
        from_attributes = True

class EventAttendanceWithUser(BaseModel):
    id: int
    event_id: int
    user_id: int
    registered_at: datetime
    attended: bool
    attended_at: Optional[datetime]
    user_name: Optional[str] = None
    user_email: Optional[str] = None
    
    class Config:
        from_attributes = True

class EventCodeResponse(BaseModel):
    event_id: int
    code: str  # 4-значный код

# FastAPI приложение
app = FastAPI(title="Event Service", version="1.0.0")

async def apply_migration():
    """Применить миграцию для добавления новых колонок в таблицу events"""
    from services.shared.database import execute_migration_sql
    
    migration_sql = """
    -- Добавить колонки для QR кода, если их нет
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='events' AND column_name='qr_token') THEN
            ALTER TABLE events ADD COLUMN qr_token VARCHAR(100);
        END IF;
        
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='events' AND column_name='qr_token_generated_at') THEN
            ALTER TABLE events ADD COLUMN qr_token_generated_at TIMESTAMP WITH TIME ZONE;
        END IF;
    END $$;

    -- Создать таблицу event_groups, если её нет
    CREATE TABLE IF NOT EXISTS event_groups (
        event_id INTEGER NOT NULL,
        group_id INTEGER NOT NULL,
        PRIMARY KEY (event_id, group_id),
        FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE,
        FOREIGN KEY (group_id) REFERENCES student_groups(id) ON DELETE CASCADE
    );
    """
    await execute_migration_sql(migration_sql)

_miss_worker_task = None

@app.on_event("startup")
async def startup():
    global _miss_worker_task
    await init_db()
    # Применить миграцию для добавления новых колонок
    await apply_migration()
    await apply_hackathon_migrations()
    if _miss_worker_task is None or _miss_worker_task.done():
        _miss_worker_task = asyncio.create_task(streak_service.lesson_miss_worker())

@app.on_event("shutdown")
async def shutdown():
    if _miss_worker_task and not _miss_worker_task.done():
        _miss_worker_task.cancel()

# Новые модули: отметка на занятии, серии посещений, тестовый импорт расписания
app.include_router(lesson_checkin.router)
app.include_router(streak_service.router)
app.include_router(schedule_import.router)
app.include_router(engagement.router)

@app.get("/")
async def root():
    return {"service": "Event Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD событий
@app.post("/events/", response_model=EventResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_event(event_in: EventCreate, db: AsyncSession = Depends(get_db)):
    """Создать событие"""
    # Создать событие
    event_data = event_in.model_dump(exclude={"group_ids"})
    event = Event(**event_data)
    db.add(event)
    await db.commit()
    await db.refresh(event)
    
    # Добавить группы, если указаны
    if event_in.group_ids:
        # Проверить существование групп
        result = await db.execute(
            select(StudentGroup).where(StudentGroup.id.in_(event_in.group_ids))
        )
        groups = result.scalars().all()
        if len(groups) != len(event_in.group_ids):
            raise HTTPException(status_code=404, detail="Одна или несколько групп не найдены")
        
        # Вставить связи напрямую в таблицу many-to-many
        await db.execute(
            insert(event_groups).values([
                {"event_id": event.id, "group_id": group_id}
                for group_id in event_in.group_ids
            ])
        )
        await db.commit()
    
    # Загрузить группы для ответа
    await db.refresh(event, ["groups"])
    return event

@app.get("/events/", response_model=List[EventResponse])
async def list_events(
    skip: int = 0,
    limit: int = 100,
    upcoming_only: bool = False,
    user_id: Optional[int] = None,
    db: AsyncSession = Depends(get_db)
):
    """Список событий"""
    query = select(Event).options(selectinload(Event.groups))
    
    if upcoming_only:
        query = query.where(Event.start_time > datetime.now(timezone.utc))
    
    if user_id:
        # Получить группы пользователя
        result = await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == user_id)
        )
        user_group_ids = [row[0] for row in result.all()]
        
        # Фильтровать события: публичные ИЛИ события групп пользователя
        if user_group_ids:
            # События, доступные пользователю
            query = query.where(
                or_(
                    Event.is_public == True,
                    Event.id.in_(
                        select(event_groups.c.event_id).where(
                            event_groups.c.group_id.in_(user_group_ids)
                        )
                    )
                )
            )
        else:
            # Если пользователь не в группах, показывать только публичные
            query = query.where(Event.is_public == True)
    
    query = query.offset(skip).limit(limit).order_by(Event.start_time)
    result = await db.execute(query)
    return result.scalars().all()

@app.get("/events/{event_id}", response_model=EventResponse)
async def get_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Получить событие по ID"""
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.groups))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    return event

@app.put("/events/{event_id}", response_model=EventResponse, dependencies=[Depends(require_admin)])
async def update_event(
    event_id: int,
    event_in: EventUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить событие"""
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.groups))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    # Обновить группы, если указаны
    if event_in.group_ids is not None:
        # Удалить все текущие связи
        await db.execute(
            delete(event_groups).where(event_groups.c.event_id == event_id)
        )
        await db.commit()
        
        # Добавить новые связи
        if event_in.group_ids:
            # Проверить существование групп
            result = await db.execute(
                select(StudentGroup).where(StudentGroup.id.in_(event_in.group_ids))
            )
            groups = result.scalars().all()
            if len(groups) != len(event_in.group_ids):
                raise HTTPException(status_code=404, detail="Одна или несколько групп не найдены")
            
            # Вставить новые связи
            await db.execute(
                insert(event_groups).values([
                    {"event_id": event_id, "group_id": group_id}
                    for group_id in event_in.group_ids
                ])
            )
            await db.commit()
    
    # Обновить остальные поля
    update_data = event_in.model_dump(exclude_unset=True, exclude={"group_ids"})
    for field, value in update_data.items():
        setattr(event, field, value)
    
    await db.commit()
    await db.refresh(event, ["groups"])
    return event

@app.delete("/events/{event_id}", response_model=EventResponse, dependencies=[Depends(require_admin)])
async def delete_event(event_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить событие"""
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.groups))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    # Сохранить данные для ответа перед удалением
    event_data = {
        "id": event.id,
        "name": event.name,
        "description": event.description,
        "location": event.location,
        "start_time": event.start_time,
        "end_time": event.end_time,
        "max_participants": event.max_participants,
        "is_public": event.is_public,
        "reward_coins": event.reward_coins,
        "reward_intelligence_points": event.reward_intelligence_points,
        "qr_token": event.qr_token,
        "created_at": event.created_at,
        "updated_at": event.updated_at,
        "groups": [{"id": g.id, "name": g.name, "description": g.description} for g in event.groups]
    }
    
    await db.delete(event)
    await db.commit()
    
    # Вернуть данные как EventResponse
    return EventResponse(**event_data)

# Регистрация и посещение
@app.post("/events/{event_id}/register")
async def register_for_event(
    event_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Зарегистрировать пользователя на событие"""
    # Проверка события
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    # Проверка пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверить, не зарегистрирован ли уже
    result = await db.execute(
        select(EventAttendance).where(and_(
            EventAttendance.event_id == event_id,
            EventAttendance.user_id == user_id
        ))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь уже зарегистрирован")
    
    # Проверить лимит участников
    if event.max_participants:
        result = await db.execute(
            select(sql_func.count(EventAttendance.id))
            .where(EventAttendance.event_id == event_id)
        )
        current_count = result.scalar()
        if current_count >= event.max_participants:
            raise HTTPException(status_code=400, detail="Достигнут лимит участников")
    
    attendance = EventAttendance(event_id=event_id, user_id=user_id)
    db.add(attendance)
    await db.commit()
    await db.refresh(attendance)
    
    return EventAttendanceResponse.model_validate(attendance)

@app.post("/events/{event_id}/attend", dependencies=[Depends(require_admin)])
async def mark_attendance(
    event_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Отметить посещение события пользователем и выдать награды
    """
    # Найти регистрацию
    result = await db.execute(
        select(EventAttendance).where(and_(
            EventAttendance.event_id == event_id,
            EventAttendance.user_id == user_id
        ))
    )
    attendance = result.scalar_one_or_none()
    
    if not attendance:
        raise HTTPException(status_code=404, detail="Пользователь не зарегистрирован на событие")
    
    if attendance.attended:
        raise HTTPException(status_code=400, detail="Посещение уже отмечено")
    
    # Получить событие для наград
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    # Отметить посещение
    attendance.attended = True
    attendance.attended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(attendance)
    
    # Выдать награды через Reward Service
    reward_service = ServiceClient("reward")
    try:
        rewards = await reward_service.post("/rewards/grant", json={
            "user_id": user_id,
            "coins": event.reward_coins,
            "intelligence_points": event.reward_intelligence_points
        })
        
        return {
            "attendance": EventAttendanceResponse.model_validate(attendance),
            "rewards": rewards
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче наград: {str(e)}")
    finally:
        await reward_service.close()

@app.get("/events/{event_id}/attendances", response_model=List[EventAttendanceWithUser])
async def get_event_attendances(
    event_id: int,
    attended_only: bool = False,
    db: AsyncSession = Depends(get_db)
):
    """Получить список участников события с информацией о пользователях"""
    query = select(EventAttendance, User).join(
        User, EventAttendance.user_id == User.id
    ).where(EventAttendance.event_id == event_id)
    
    if attended_only:
        query = query.where(EventAttendance.attended == True)
    
    result = await db.execute(query)
    attendances_with_users = []
    rows = result.all()
    for row in rows:
        attendance = row[0]
        user = row[1]
        attendances_with_users.append(EventAttendanceWithUser(
            id=attendance.id,
            event_id=attendance.event_id,
            user_id=attendance.user_id,
            registered_at=attendance.registered_at,
            attended=attendance.attended,
            attended_at=attendance.attended_at,
            user_name=user.username if user else None,
            user_email=user.email if user else None
        ))
    return attendances_with_users

@app.get("/events/{event_id}/user/{user_id}/attendance", response_model=Optional[EventAttendanceResponse])
async def get_user_event_attendance(
    event_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Получить информацию о регистрации пользователя на событие"""
    result = await db.execute(
        select(EventAttendance).where(and_(
            EventAttendance.event_id == event_id,
            EventAttendance.user_id == user_id
        ))
    )
    attendance = result.scalar_one_or_none()
    if attendance:
        return EventAttendanceResponse.model_validate(attendance)
    return None

@app.get("/events/users/{user_id}", response_model=List[EventAttendanceResponse])
async def get_user_event_attendances(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить события пользователя"""
    result = await db.execute(
        select(EventAttendance)
        .where(EventAttendance.user_id == user_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

@app.get("/events/stats/{user_id}")
async def get_user_event_statistics(user_id: int, db: AsyncSession = Depends(get_db)):
    """Статистика по событиям пользователя"""
    # Получить все регистрации пользователя
    result = await db.execute(
        select(EventAttendance).where(EventAttendance.user_id == user_id)
    )
    attendances = result.scalars().all()
    
    registered_count = len(attendances)
    attended_count = sum(1 for a in attendances if a.attended)
    
    return {
        "user_id": user_id,
        "registered_events": registered_count,
        "attended_events": attended_count,
        "attendance_rate": round(attended_count / registered_count * 100, 2) if registered_count > 0 else 0
    }

@app.delete("/events/{event_id}/unregister/{user_id}")
async def unregister_from_event(
    event_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отменить регистрацию на событие"""
    result = await db.execute(
        select(EventAttendance).where(and_(
            EventAttendance.event_id == event_id,
            EventAttendance.user_id == user_id
        ))
    )
    attendance = result.scalar_one_or_none()
    
    if not attendance:
        raise HTTPException(status_code=404, detail="Регистрация не найдена")
    
    if attendance.attended:
        raise HTTPException(status_code=400, detail="Нельзя отменить регистрацию после посещения")
    
    await db.delete(attendance)
    return {"success": True, "event_id": event_id, "user_id": user_id}

# ===== КОДЫ ДЛЯ СОБЫТИЙ =====
@app.get("/events/{event_id}/code", response_model=EventCodeResponse, dependencies=[Depends(require_admin)])
async def get_event_code(event_id: int, db: AsyncSession = Depends(get_db)):
    """Получить 4-значный код для события с ротацией каждые 15 секунд"""
    
    result = await db.execute(select(Event).where(Event.id == event_id))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    # Проверить, нужно ли генерировать новый код (каждые 15 секунд)
    now = datetime.now(timezone.utc)
    should_generate_new = False
    
    if not event.qr_token or not event.qr_token_generated_at:
        should_generate_new = True
    else:
        # Убедиться, что оба datetime имеют timezone
        token_time = event.qr_token_generated_at
        if token_time.tzinfo is None:
            # Если время без timezone, считать его UTC
            token_time = token_time.replace(tzinfo=timezone.utc)
        time_diff = (now - token_time).total_seconds()
        if time_diff > 15:  # Изменено с 30 на 15 секунд
            should_generate_new = True
    
    if should_generate_new:
        # Генерировать новый 4-значный код
        code = f"{random.randint(1000, 9999)}"
        event.qr_token = code
        event.qr_token_generated_at = now
        await db.commit()
        await db.refresh(event)
    else:
        code = event.qr_token
    
    return EventCodeResponse(
        event_id=event_id,
        code=code
    )


class VerifyCodeRequest(BaseModel):
    code: str

@app.post("/events/{event_id}/verify-code")
async def verify_event_code(
    event_id: int,
    user_id: int,
    request: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db)
):
    """Проверить 4-значный код события и отметить посещение"""
    code = request.code
    # Получить событие с группами
    result = await db.execute(
        select(Event)
        .options(selectinload(Event.groups))
        .where(Event.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Событие не найдено")
    
    # Проверка валидности кода: код меняется каждые 15 с, принимаем не старше 45 с
    if not event.qr_token or event.qr_token != code:
        raise HTTPException(status_code=400, detail="Неверный код")
    generated_at = event.qr_token_generated_at
    if generated_at is not None:
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc) - generated_at).total_seconds() > 45:
            raise HTTPException(status_code=400, detail="Код устарел — введите код, который сейчас на экране")
    
    # Проверка доступа пользователя
    if not event.is_public:
        # Если событие не публичное, проверить группы
        event_group_ids = [g.id for g in event.groups]
        if not event_group_ids:
            raise HTTPException(status_code=400, detail="Событие не связано с группами")
        
        # Проверить, что пользователь состоит в группе события
        result = await db.execute(
            select(GroupMember).where(
                and_(
                    GroupMember.group_id.in_(event_group_ids),
                    GroupMember.user_id == user_id
                )
            )
        )
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=403, detail="Вы не имеете доступа к этому событию")
    
    # Проверка пользователя
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Найти или создать регистрацию
    result = await db.execute(
        select(EventAttendance).where(and_(
            EventAttendance.event_id == event_id,
            EventAttendance.user_id == user_id
        ))
    )
    attendance = result.scalar_one_or_none()
    
    if not attendance:
        # Автоматически создать регистрацию
        attendance = EventAttendance(event_id=event_id, user_id=user_id)
        db.add(attendance)
        await db.commit()
        await db.refresh(attendance)
    
    # Проверить, не отмечено ли уже посещение
    if attendance.attended:
        raise HTTPException(status_code=400, detail="Посещение уже отмечено")
    
    # Отметить посещение
    attendance.attended = True
    attendance.attended_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(attendance)
    
    # Выдать награды через Reward Service
    reward_service = ServiceClient("reward")
    try:
        rewards = await reward_service.post("/rewards/grant", json={
            "user_id": user_id,
            "coins": event.reward_coins,
            "intelligence_points": event.reward_intelligence_points
        })
        
        return {
            "attendance": EventAttendanceResponse.model_validate(attendance),
            "rewards": rewards
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при выдаче наград: {str(e)}")
    finally:
        await reward_service.close()

# ===== ЗАНЯТИЯ =====
class LessonCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    start_time: datetime
    end_time: datetime
    reward_coins: int = Field(default=0, ge=0)
    reward_intelligence_points: int = Field(default=0, ge=0)
    reward_satisfaction: int = Field(default=5, ge=0, le=50)
    is_simulated: bool = False
    group_ids: Optional[List[int]] = Field(default=None, description="Список ID групп для занятия")
    created_by: int

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def _to_utc(cls, value):
        # Время без часового пояса из формы — это локальное время организации
        return local_to_utc(value)

class LessonUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    location: Optional[str] = Field(None, max_length=200)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    reward_coins: Optional[int] = Field(None, ge=0)
    reward_intelligence_points: Optional[int] = Field(None, ge=0)
    reward_satisfaction: Optional[int] = Field(None, ge=0, le=50)
    is_simulated: Optional[bool] = None
    group_ids: Optional[List[int]] = Field(None, description="Список ID групп для занятия")

    @field_validator("start_time", "end_time", mode="after")
    @classmethod
    def _to_utc(cls, value):
        return local_to_utc(value)

class StudentGroupBasic(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    
    class Config:
        from_attributes = True

class LessonResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    location: Optional[str]
    start_time: datetime
    end_time: datetime
    qr_token: Optional[str] = None
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int = 5
    source: str = "manual"
    is_simulated: bool = False
    created_by: int
    created_at: datetime
    updated_at: Optional[datetime]
    groups: List[StudentGroupBasic] = []

    @field_validator("qr_token", mode="before")
    @classmethod
    def _hide_code(cls, value):
        # Код занятия вычисляется на лету и виден только преподавателю (/lessons/{id}/qr)
        return None

    class Config:
        from_attributes = True

class LessonAttendanceResponse(BaseModel):
    id: int
    lesson_id: int
    user_id: int
    attended_at: datetime
    verification_method: str

    @field_validator("verification_method", mode="before")
    @classmethod
    def _enum_value(cls, value):
        return value.value if hasattr(value, "value") else value

    class Config:
        from_attributes = True

# CRUD занятий
@app.post("/lessons/", response_model=LessonResponse, status_code=201, dependencies=[Depends(require_admin)])
async def create_lesson(lesson_in: LessonCreate, db: AsyncSession = Depends(get_db)):
    """Создать занятие"""
    from services.shared.models.lesson import lesson_groups
    
    # Проверка пользователя
    result = await db.execute(select(User).where(User.id == lesson_in.created_by))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Создать занятие
    lesson_data = lesson_in.model_dump(exclude={"group_ids", "created_by"})
    lesson = Lesson(**lesson_data, created_by=lesson_in.created_by, qr_secret=attendance_codes.new_secret())
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    
    # Добавить группы, если указаны (работаем с таблицей напрямую)
    if lesson_in.group_ids:
        # Проверить существование групп
        result = await db.execute(
            select(StudentGroup).where(StudentGroup.id.in_(lesson_in.group_ids))
        )
        groups = result.scalars().all()
        if len(groups) != len(lesson_in.group_ids):
            raise HTTPException(status_code=404, detail="Одна или несколько групп не найдены")
        
        # Вставить связи напрямую в таблицу many-to-many
        from sqlalchemy import insert
        await db.execute(
            insert(lesson_groups).values([
                {"lesson_id": lesson.id, "group_id": group_id}
                for group_id in lesson_in.group_ids
            ])
        )
        await db.commit()
    
    # Загрузить группы для ответа
    await db.refresh(lesson, ["groups"])
    return lesson

@app.get("/lessons/", response_model=List[LessonResponse])
async def list_lessons(
    user_id: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Список занятий"""
    if user_id:
        # Получить занятия для пользователя по его группам
        result = await db.execute(
            select(GroupMember.group_id).where(GroupMember.user_id == user_id)
        )
        group_ids = [row[0] for row in result.all()]
        
        if not group_ids:
            return []
        
        # Получить занятия, связанные с этими группами
        result = await db.execute(
            select(Lesson)
            .join(Lesson.groups)
            .where(StudentGroup.id.in_(group_ids))
            .options(selectinload(Lesson.groups))
            .distinct()
            .offset(skip)
            .limit(limit)
        )
        lessons = result.scalars().all()
    else:
        # Получить все занятия
        result = await db.execute(
            select(Lesson)
            .options(selectinload(Lesson.groups))
            .offset(skip)
            .limit(limit)
        )
        lessons = result.scalars().all()
    
    return lessons

@app.get("/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(lesson_id: int, db: AsyncSession = Depends(get_db)):
    """Получить занятие по ID"""
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.groups))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")
    return lesson

@app.put("/lessons/{lesson_id}", response_model=LessonResponse, dependencies=[Depends(require_admin)])
async def update_lesson(
    lesson_id: int,
    lesson_in: LessonUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить занятие"""
    from services.shared.models.lesson import lesson_groups
    from sqlalchemy import delete, insert
    
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.groups))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")
    
    # Обновить группы, если указаны
    if lesson_in.group_ids is not None:
        # Удалить все текущие связи
        await db.execute(
            delete(lesson_groups).where(lesson_groups.c.lesson_id == lesson_id)
        )
        await db.commit()
        
        # Добавить новые связи
        if lesson_in.group_ids:
            # Проверить существование групп
            result = await db.execute(
                select(StudentGroup).where(StudentGroup.id.in_(lesson_in.group_ids))
            )
            groups = result.scalars().all()
            if len(groups) != len(lesson_in.group_ids):
                raise HTTPException(status_code=404, detail="Одна или несколько групп не найдены")
            
            # Вставить новые связи
            await db.execute(
                insert(lesson_groups).values([
                    {"lesson_id": lesson_id, "group_id": group_id}
                    for group_id in lesson_in.group_ids
                ])
            )
            await db.commit()
    
    # Обновить остальные поля
    update_data = lesson_in.model_dump(exclude_unset=True, exclude={"group_ids"})
    for field, value in update_data.items():
        setattr(lesson, field, value)
    
    await db.commit()
    await db.refresh(lesson, ["groups"])
    return lesson

@app.delete("/lessons/{lesson_id}", response_model=LessonResponse, dependencies=[Depends(require_admin)])
async def delete_lesson(lesson_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить занятие"""
    result = await db.execute(
        select(Lesson)
        .options(selectinload(Lesson.groups))
        .where(Lesson.id == lesson_id)
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(status_code=404, detail="Занятие не найдено")
    
    # Сохранить данные для ответа перед удалением
    lesson_data = {
        "id": lesson.id,
        "name": lesson.name,
        "description": lesson.description,
        "location": lesson.location,
        "start_time": lesson.start_time,
        "end_time": lesson.end_time,
        "qr_token": lesson.qr_token,
        "reward_coins": lesson.reward_coins,
        "reward_intelligence_points": lesson.reward_intelligence_points,
        "reward_satisfaction": lesson.reward_satisfaction,
        "source": lesson.source,
        "is_simulated": lesson.is_simulated,
        "created_by": lesson.created_by,
        "created_at": lesson.created_at,
        "updated_at": lesson.updated_at,
        "groups": [{"id": g.id, "name": g.name, "description": g.description} for g in lesson.groups]
    }
    
    await db.delete(lesson)
    await db.commit()
    
    # Вернуть данные как LessonResponse
    return LessonResponse(**lesson_data)

# QR-код, отметка и ручная отметка занятий — см. lesson_checkin.py

@app.get("/lessons/{lesson_id}/attendance", response_model=List[LessonAttendanceResponse])
async def get_lesson_attendances(
    lesson_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить посещения занятия"""
    result = await db.execute(
        select(LessonAttendance)
        .where(LessonAttendance.lesson_id == lesson_id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)

