"""
Social Service - Управление социальными взаимодействиями
Порт: 8007
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func as sql_func
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from services.shared.database import get_db, init_db, engine
from sqlalchemy import text
from services.shared.models.social import (
    Friendship, FriendshipStatus,
    StudentGroup, GroupMember, GroupInvitation, GroupInvitationStatus
)
from services.shared.models.user import User
# Импортируем TaskGeneration для корректной инициализации relationship в User
from services.shared.models.task_generation import TaskGeneration
from services.shared.utils import ServiceClient
from services.shared.realtime import push_user_event
import logging

logger = logging.getLogger(__name__)

# Pydantic схемы
class FriendshipUserInfo(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        from_attributes = True


class FriendshipResponse(BaseModel):
    id: int
    user_id: int
    friend_id: int
    status: FriendshipStatus
    created_at: datetime
    accepted_at: Optional[datetime]
    user: FriendshipUserInfo
    friend: FriendshipUserInfo
    
    class Config:
        from_attributes = True
        use_enum_values = True


class FriendCandidateResponse(BaseModel):
    id: int
    username: str
    email: str
    friendship_id: Optional[int] = None
    friendship_status: Optional[FriendshipStatus] = None
    is_incoming: bool = False
    is_outgoing: bool = False

    class Config:
        from_attributes = True
        use_enum_values = True

class StudentGroupCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None

class StudentGroupUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None

class StudentGroupResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    creator_id: Optional[int]
    created_at: datetime
    updated_at: Optional[datetime]
    members: List['GroupMemberResponse'] = []
    
    class Config:
        from_attributes = True

class GroupMemberUserInfo(BaseModel):
    id: int
    username: str
    email: str
    
    class Config:
        from_attributes = True

class GroupMemberResponse(BaseModel):
    id: int
    group_id: int
    user_id: int
    joined_at: datetime
    user: Optional[GroupMemberUserInfo] = None
    
    class Config:
        from_attributes = True

class GroupInvitationResponse(BaseModel):
    id: int
    group_id: int
    user_id: int
    inviter_id: int
    status: GroupInvitationStatus
    created_at: datetime
    updated_at: Optional[datetime]
    responded_at: Optional[datetime]
    group: Optional[StudentGroupResponse] = None
    
    class Config:
        from_attributes = True
        use_enum_values = True

# Обновляем forward references
StudentGroupResponse.model_rebuild()

# FastAPI приложение
app = FastAPI(title="Social Service", version="1.0.0")

async def apply_migration():
    """Применить миграцию для добавления creator_id и создания таблицы group_invitations"""
    from services.shared.database import execute_migration_sql
    
    migration_sql = """
    -- Добавить колонку creator_id в таблицу student_groups, если её нет
    DO $$ 
    BEGIN
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns 
                       WHERE table_name='student_groups' AND column_name='creator_id') THEN
            ALTER TABLE student_groups ADD COLUMN creator_id INTEGER;
            
            -- Создать индекс для creator_id
            CREATE INDEX IF NOT EXISTS ix_student_groups_creator_id ON student_groups(creator_id);
            
            -- Добавить внешний ключ
            ALTER TABLE student_groups 
            ADD CONSTRAINT fk_student_groups_creator_id 
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE SET NULL;
            
            -- Установить creator_id для существующих групп на первого участника (если есть)
            UPDATE student_groups sg
            SET creator_id = (
                SELECT gm.user_id 
                FROM group_members gm 
                WHERE gm.group_id = sg.id 
                ORDER BY gm.joined_at ASC 
                LIMIT 1
            )
            WHERE creator_id IS NULL 
            AND EXISTS (SELECT 1 FROM group_members WHERE group_id = sg.id);
        END IF;
    END $$;

    -- Создать таблицу group_invitations, если её нет
    CREATE TABLE IF NOT EXISTS group_invitations (
        id SERIAL PRIMARY KEY,
        group_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        inviter_id INTEGER NOT NULL,
        status VARCHAR(20) NOT NULL DEFAULT 'pending',
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE,
        responded_at TIMESTAMP WITH TIME ZONE,
        FOREIGN KEY (group_id) REFERENCES student_groups(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (inviter_id) REFERENCES users(id) ON DELETE CASCADE,
        CONSTRAINT chk_group_invitations_status CHECK (status IN ('pending', 'accepted', 'rejected'))
    );

    -- Создать индексы для group_invitations
    CREATE INDEX IF NOT EXISTS ix_group_invitations_group_id ON group_invitations(group_id);
    CREATE INDEX IF NOT EXISTS ix_group_invitations_user_id ON group_invitations(user_id);
    CREATE INDEX IF NOT EXISTS ix_group_invitations_inviter_id ON group_invitations(inviter_id);
    CREATE INDEX IF NOT EXISTS ix_group_invitations_status ON group_invitations(status);
    """
    await execute_migration_sql(migration_sql)

@app.on_event("startup")
async def startup():
    await init_db()
    # Применить миграцию для добавления creator_id и создания таблицы group_invitations
    await apply_migration()

@app.get("/")
async def root():
    return {"service": "Social Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# ===== ДРУЖБА =====
@app.post("/friendships/request")
async def send_friend_request(
    user_id: int,
    friend_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отправить запрос на дружбу"""
    if user_id == friend_id:
        raise HTTPException(status_code=400, detail="Нельзя добавить себя в друзья")
    
    # Проверка существования пользователей
    for uid in [user_id, friend_id]:
        result = await db.execute(select(User).where(User.id == uid))
        if not result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail=f"Пользователь {uid} не найден")
    
    # Проверить, нет ли уже запроса
    result = await db.execute(
        select(Friendship).where(or_(
            and_(Friendship.user_id == user_id, Friendship.friend_id == friend_id),
            and_(Friendship.user_id == friend_id, Friendship.friend_id == user_id)
        ))
    )
    existing = result.scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="Запрос уже существует или пользователи уже друзья")
    
    friendship = Friendship(user_id=user_id, friend_id=friend_id, status=FriendshipStatus.PENDING)
    db.add(friendship)
    await db.commit()
    await db.refresh(friendship, attribute_names=["user", "friend"])
    
    # Отправляем уведомление получателю
    initiator_username = None
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == user_id))
        initiator = result.scalar_one_or_none()
        initiator_username = initiator.username if initiator else None
        await bot_service.post("/notifications/friend-request", json={
            "recipient_user_id": friend_id,
            "initiator_user_id": user_id,
            "friendship_id": friendship.id,
            "initiator_username": initiator_username
        })
        await bot_service.close()
    except Exception as e:
        # Логируем ошибку, но не прерываем основную операцию
        logger.warning(f"Не удалось отправить уведомление о запросе дружбы: {e}")
    
    # Публикуем событие в realtime-сервис для показа badge
    await push_user_event(
        friend_id,
        "social.friend_request.received",
        payload={
            "friendship_id": friendship.id,
            "initiator_user_id": user_id,
            "initiator_username": initiator_username,
        },
        metadata={"source": "social_service"},
    )

    return FriendshipResponse.model_validate(friendship)

@app.post("/friendships/{friendship_id}/accept")
async def accept_friend_request(
    friendship_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Принять запрос на дружбу"""
    try:
        logger.info(f"Принятие запроса дружбы friendship_id={friendship_id}")
        result = await db.execute(select(Friendship).where(Friendship.id == friendship_id))
        friendship = result.scalar_one_or_none()
        if not friendship:
            logger.error(f"Запрос дружбы {friendship_id} не найден")
            raise HTTPException(status_code=404, detail="Запрос не найден")
        
        logger.info(f"Найден запрос дружбы: user_id={friendship.user_id}, friend_id={friendship.friend_id}, status={friendship.status}")
        
        if friendship.status != FriendshipStatus.PENDING:
            logger.warning(f"Запрос дружбы {friendship_id} уже обработан, статус={friendship.status}")
            raise HTTPException(status_code=400, detail="Запрос уже обработан")
        
        friendship.status = FriendshipStatus.ACCEPTED
        friendship.accepted_at = datetime.now()
        await db.commit()
        await db.refresh(friendship, attribute_names=["user", "friend"])
        logger.info(f"Запрос дружбы {friendship_id} успешно принят")
        
        # Отправляем уведомление инициатору о принятии запроса
        try:
            bot_service = ServiceClient("max_bot")
            result = await db.execute(select(User).where(User.id == friendship.friend_id))
            acceptor = result.scalar_one_or_none()
            acceptor_username = acceptor.username if acceptor else None
            await bot_service.post("/notifications/friend-request-accepted", json={
                "initiator_user_id": friendship.user_id,
                "acceptor_username": acceptor_username
            })
            await bot_service.close()
            logger.info(f"Уведомление о принятии запроса отправлено инициатору {friendship.user_id}")
        except Exception as e:
            # Логируем ошибку, но не прерываем основную операцию
            logger.warning(f"Не удалось отправить уведомление о принятии запроса дружбы: {e}", exc_info=True)
        
        return FriendshipResponse.model_validate(friendship)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при принятии запроса дружбы {friendship_id}: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при принятии запроса дружбы: {str(e)}")

@app.delete("/friendships/{friendship_id}")
async def delete_friendship(friendship_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить дружбу или отклонить запрос"""
    result = await db.execute(select(Friendship).where(Friendship.id == friendship_id))
    friendship = result.scalar_one_or_none()
    if not friendship:
        raise HTTPException(status_code=404, detail="Дружба не найдена")
    
    await db.delete(friendship)
    await db.commit()
    return {"success": True, "friendship_id": friendship_id}

@app.get("/friendships/users/{user_id}")
async def get_user_friends(
    user_id: int,
    status: Optional[FriendshipStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить друзей пользователя"""
    query = (
        select(Friendship)
        .options(joinedload(Friendship.user), joinedload(Friendship.friend))
        .where(or_(
            Friendship.user_id == user_id,
            Friendship.friend_id == user_id
        ))
    )
    
    if status:
        query = query.where(Friendship.status == status)
    
    result = await db.execute(query)
    friendships = result.scalars().all()
    
    return [FriendshipResponse.model_validate(f) for f in friendships]


@app.get("/friendships/search", response_model=List[FriendCandidateResponse])
async def search_friend_candidates(
    query: str = Query(..., min_length=1, description="Строка поиска (логин или email)"),
    user_id: int = Query(..., ge=1, description="ID текущего пользователя"),
    limit: int = Query(10, ge=1, le=50, description="Максимум результатов"),
    db: AsyncSession = Depends(get_db)
):
    """Поиск пользователей для добавления в друзья."""
    search_value = query.strip()
    if not search_value:
        return []
    
    pattern = f"%{search_value.lower()}%"
    
    users_result = await db.execute(
        select(User)
        .where(
            and_(
                User.id != user_id,
                or_(
                    sql_func.lower(User.username).like(pattern),
                    sql_func.lower(User.email).like(pattern)
                )
            )
        )
        .order_by(sql_func.lower(User.username))
        .limit(limit)
    )
    
    candidates = list(users_result.scalars().all())
    if not candidates:
        return []
    
    candidate_ids = [candidate.id for candidate in candidates]
    
    friendships_result = await db.execute(
        select(Friendship)
        .where(
            or_(
                and_(
                    Friendship.user_id == user_id,
                    Friendship.friend_id.in_(candidate_ids)
                ),
                and_(
                    Friendship.friend_id == user_id,
                    Friendship.user_id.in_(candidate_ids)
                )
            )
        )
    )
    existing_friendships = {(
        friendship.friend_id if friendship.user_id == user_id else friendship.user_id
    ): friendship for friendship in friendships_result.scalars().all()}
    
    responses: List[FriendCandidateResponse] = []
    for candidate in candidates:
        friendship = existing_friendships.get(candidate.id)
        friendship_status = friendship.status if friendship else None
        responses.append(
            FriendCandidateResponse(
                id=candidate.id,
                username=candidate.username,
                email=candidate.email,
                friendship_id=friendship.id if friendship else None,
                friendship_status=friendship_status,
                is_incoming=bool(
                    friendship
                    and friendship.friend_id == user_id
                    and friendship.status == FriendshipStatus.PENDING
                ),
                is_outgoing=bool(
                    friendship
                    and friendship.user_id == user_id
                    and friendship.status == FriendshipStatus.PENDING
                ),
            )
        )
    
    return responses

# ===== УЧЕБНЫЕ ГРУППЫ =====
@app.post("/groups/", response_model=StudentGroupResponse, status_code=201)
async def create_student_group(
    group_in: StudentGroupCreate,
    creator_id: int = Query(..., description="ID создателя группы"),
    db: AsyncSession = Depends(get_db)
):
    """Создать учебную группу"""
    try:
        logger.info(f"Создание группы: name={group_in.name}, creator_id={creator_id}")
        
        # Проверка существования создателя
        result = await db.execute(select(User).where(User.id == creator_id))
        creator = result.scalar_one_or_none()
        if not creator:
            logger.error(f"Создатель группы {creator_id} не найден")
            raise HTTPException(status_code=404, detail="Создатель группы не найден")
        
        logger.info(f"Создатель найден: {creator.username}")
        
        # Проверка уникальности
        result = await db.execute(select(StudentGroup).where(StudentGroup.name == group_in.name))
        if result.scalar_one_or_none():
            logger.warning(f"Группа с именем '{group_in.name}' уже существует")
            raise HTTPException(status_code=400, detail="Группа с таким именем уже существует")
        
        # Создаем группу с creator_id
        group_data = group_in.model_dump()
        group_data["creator_id"] = creator_id
        group = StudentGroup(**group_data)
        db.add(group)
        try:
            await db.flush()  # Получаем ID группы
        except Exception as flush_error:
            # Если колонка creator_id не существует, попробуем создать без неё
            error_str = str(flush_error).lower()
            if "creator_id" in error_str or "column" in error_str:
                logger.warning(f"Колонка creator_id еще не создана. Создаю группу без creator_id. Выполните миграцию migrate_groups_invitations.sql. Ошибка: {flush_error}")
                await db.rollback()
                # Создаем группу без creator_id
                group_data_no_creator = group_in.model_dump()
                group = StudentGroup(**group_data_no_creator)
                db.add(group)
                await db.flush()
            else:
                raise
        
        # Автоматически добавляем создателя как участника
        logger.info(f"Добавление создателя {creator_id} как участника группы {group.id}")
        creator_member = GroupMember(group_id=group.id, user_id=creator_id)
        db.add(creator_member)
        await db.commit()
        logger.info(f"Группа {group.id} успешно создана и создатель добавлен как участник")
        
        # Загружаем группу с участниками и информацией о пользователях для ответа
        logger.info(f"Загрузка группы {group.id} с участниками для ответа")
        try:
            result = await db.execute(
                select(StudentGroup)
                .where(StudentGroup.id == group.id)
                .options(
                    selectinload(StudentGroup.members).joinedload(GroupMember.user)
                )
            )
            group = result.scalar_one()
            logger.info(f"Группа {group.id} загружена, участников: {len(group.members)}")
            
            # Пробуем сериализовать ответ для проверки
            try:
                response = StudentGroupResponse.model_validate(group)
                logger.info(f"Ответ успешно сериализован для группы {group.id}")
            except Exception as serialization_error:
                logger.error(f"Ошибка сериализации ответа для группы {group.id}: {serialization_error}", exc_info=True)
                # Возвращаем группу без сериализации, FastAPI попробует сам
                pass
            
            return group
        except Exception as load_error:
            logger.error(f"Ошибка при загрузке группы {group.id} с участниками: {load_error}", exc_info=True)
            # Пробуем вернуть группу без участников
            result = await db.execute(
                select(StudentGroup)
                .where(StudentGroup.id == group.id)
            )
            group = result.scalar_one()
            logger.warning(f"Возвращаем группу {group.id} без участников из-за ошибки загрузки")
            return group
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка при создании группы: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка при создании группы: {str(e)}")

@app.get("/groups/", response_model=List[StudentGroupResponse])
async def list_student_groups(
    user_id: Optional[int] = Query(None, description="ID пользователя для фильтрации (опционально, если не указан - возвращаются все группы)"),
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Список групп. Если указан user_id - возвращает группы пользователя (где он участник или имеет pending приглашение), иначе - все группы"""
    if user_id is not None:
        # Получаем ID групп, где пользователь является участником
        member_result = await db.execute(
            select(GroupMember.group_id)
            .where(GroupMember.user_id == user_id)
        )
        member_group_ids = {row[0] for row in member_result.fetchall()}
        
        # Получаем ID групп, где пользователь имеет pending приглашение
        try:
            invitation_result = await db.execute(
                select(GroupInvitation.group_id)
                .where(and_(
                    GroupInvitation.user_id == user_id,
                    GroupInvitation.status == GroupInvitationStatus.PENDING
                ))
            )
            invitation_group_ids = {row[0] for row in invitation_result.fetchall()}
        except Exception as e:
            # Если таблица group_invitations еще не создана, просто используем пустой список
            logger.warning(f"Ошибка при получении приглашений (возможно, таблица еще не создана): {e}")
            invitation_group_ids = set()
        
        # Объединяем ID групп
        all_group_ids = list(member_group_ids | invitation_group_ids)
        
        if not all_group_ids:
            return []
        
        # Получаем группы с участниками и информацией о пользователях
        result = await db.execute(
            select(StudentGroup)
            .options(
                selectinload(StudentGroup.members).joinedload(GroupMember.user)
            )
            .where(StudentGroup.id.in_(all_group_ids))
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()
    else:
        # Возвращаем все группы (для админки)
        result = await db.execute(
            select(StudentGroup)
            .options(
                selectinload(StudentGroup.members).joinedload(GroupMember.user)
            )
            .offset(skip)
            .limit(limit)
        )
        return result.scalars().all()

@app.get("/groups/{group_id}", response_model=StudentGroupResponse)
async def get_student_group(group_id: int, db: AsyncSession = Depends(get_db)):
    """Получить учебную группу по ID"""
    result = await db.execute(
        select(StudentGroup)
        .options(
            selectinload(StudentGroup.members).joinedload(GroupMember.user)
        )
        .where(StudentGroup.id == group_id)
    )
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    return group

@app.delete("/groups/{group_id}")
async def delete_student_group(
    group_id: int,
    requester_id: int = Query(..., description="ID пользователя, который удаляет (должен быть создателем группы)"),
    db: AsyncSession = Depends(get_db)
):
    """Удалить группу (только создатель)"""
    result = await db.execute(select(StudentGroup).where(StudentGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    # Проверка, что запрашивающий является создателем группы
    if group.creator_id != requester_id:
        raise HTTPException(status_code=403, detail="Только создатель группы может удалить группу")
    
    await db.delete(group)
    await db.commit()
    return {"success": True, "group_id": group_id, "message": "Группа удалена"}

@app.get("/groups/{group_id}/members", response_model=List[GroupMemberResponse])
async def get_group_members(
    group_id: int,
    user_id: int = Query(..., description="ID пользователя, который запрашивает список (должен быть участником или создателем)"),
    db: AsyncSession = Depends(get_db)
):
    """Получить членов группы (доступно участникам и создателю)"""
    # Проверка существования группы
    result = await db.execute(select(StudentGroup).where(StudentGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    # Проверка, что пользователь является участником или создателем
    is_creator = group.creator_id == user_id
    result = await db.execute(
        select(GroupMember).where(and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ))
    )
    is_member = result.scalar_one_or_none() is not None
    
    if not (is_creator or is_member):
        raise HTTPException(status_code=403, detail="Только участники группы могут видеть список участников")
    
    # Загружаем участников с информацией о пользователях
    result = await db.execute(
        select(GroupMember)
        .options(joinedload(GroupMember.user))
        .where(GroupMember.group_id == group_id)
    )
    members = result.scalars().unique().all()
    # Убеждаемся, что возвращаем список (даже если пустой) - FastAPI может не сериализовать пустой список правильно
    members_list = list(members) if members else []
    # Явно возвращаем JSONResponse для пустого списка
    if not members_list:
        return JSONResponse(content=[])
    return members_list

@app.post("/groups/{group_id}/members/add")
async def add_group_member(
    group_id: int,
    user_id: int = Query(..., description="ID пользователя"),
    inviter_user_id: int = Query(..., description="ID пользователя, который приглашает (должен быть создателем группы)"),
    db: AsyncSession = Depends(get_db)
):
    """Пригласить пользователя в группу (создает приглашение)"""
    # Проверки
    result = await db.execute(select(StudentGroup).where(StudentGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    # Проверка, что приглашающий является создателем группы
    if group.creator_id != inviter_user_id:
        raise HTTPException(status_code=403, detail="Только создатель группы может приглашать пользователей")
    
    result = await db.execute(select(User).where(User.id == user_id))
    invited_user = result.scalar_one_or_none()
    if not invited_user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверить, не состоит ли уже в группе
    result = await db.execute(
        select(GroupMember).where(and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Пользователь уже в группе")
    
    # Проверить, нет ли уже pending приглашения
    result = await db.execute(
        select(GroupInvitation).where(and_(
            GroupInvitation.group_id == group_id,
            GroupInvitation.user_id == user_id,
            GroupInvitation.status == GroupInvitationStatus.PENDING
        ))
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Приглашение уже отправлено")
    
    # Создаем приглашение
    invitation = GroupInvitation(
        group_id=group_id,
        user_id=user_id,
        inviter_id=inviter_user_id,
        status=GroupInvitationStatus.PENDING
    )
    db.add(invitation)
    await db.commit()
    await db.refresh(invitation)
    
    logger.info(f"Создано приглашение: id={invitation.id}, group_id={group_id}, user_id={user_id}, inviter_id={inviter_user_id}, status={invitation.status}")
    
    # Отправляем уведомление в ВК приглашенному пользователю
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == inviter_user_id))
        inviter = result.scalar_one_or_none()
        inviter_username = inviter.username if inviter else None
        
        notification_data = {
            "recipient_user_id": user_id,
            "inviter_user_id": inviter_user_id,
            "group_id": group_id,
            "group_name": group.name,
            "inviter_username": inviter_username,
            "invitation_id": invitation.id
        }
        
        logger.info(f"Отправка уведомления о приглашении в группу: {notification_data}")
        response = await bot_service.post("/notifications/group-invitation", json=notification_data)
        logger.info(f"Ответ от сервиса уведомлений: {response}")
        await bot_service.close()
    except Exception as e:
        # Логируем ошибку, но не прерываем основную операцию
        logger.error(f"Не удалось отправить уведомление о приглашении в группу: {e}", exc_info=True)
    
    return {
        "id": invitation.id,
        "group_id": invitation.group_id,
        "user_id": invitation.user_id,
        "inviter_id": invitation.inviter_id,
        "status": invitation.status.value,
        "created_at": invitation.created_at
    }

@app.delete("/groups/{group_id}/members/{user_id}")
async def remove_group_member(
    group_id: int,
    user_id: int,
    requester_id: int = Query(..., description="ID пользователя, который удаляет (должен быть создателем группы)"),
    db: AsyncSession = Depends(get_db)
):
    """Удалить пользователя из группы (только создатель)"""
    # Проверка существования группы
    result = await db.execute(select(StudentGroup).where(StudentGroup.id == group_id))
    group = result.scalar_one_or_none()
    if not group:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    
    # Проверка, что запрашивающий является создателем группы
    if group.creator_id != requester_id:
        raise HTTPException(status_code=403, detail="Только создатель группы может удалять участников")
    
    result = await db.execute(
        select(GroupMember).where(and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ))
    )
    member = result.scalar_one_or_none()
    if not member:
        raise HTTPException(status_code=404, detail="Член группы не найден")
    
    # Нельзя удалить создателя из группы
    if user_id == group.creator_id:
        raise HTTPException(status_code=400, detail="Нельзя удалить создателя группы")
    
    await db.delete(member)
    await db.commit()
    return {"success": True, "group_id": group_id, "user_id": user_id}

@app.get("/groups/{group_id}/members/{user_id}/check")
async def check_group_membership(
    group_id: int,
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Проверить, является ли пользователь участником группы"""
    result = await db.execute(
        select(GroupMember).where(and_(
            GroupMember.group_id == group_id,
            GroupMember.user_id == user_id
        ))
    )
    member = result.scalar_one_or_none()
    return {
        "is_member": member is not None,
        "member": GroupMemberResponse.model_validate(member) if member else None
    }

# ===== ПРИГЛАШЕНИЯ В ГРУППЫ =====
@app.get("/groups/invitations/user/{user_id}", response_model=List[GroupInvitationResponse])
async def get_user_invitations(
    user_id: int,
    status: Optional[GroupInvitationStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить приглашения пользователя"""
    try:
        logger.info(f"Получение приглашений для пользователя {user_id}, статус: {status}")
        
        # Загружаем приглашения с информацией о группе
        query = (
            select(GroupInvitation)
            .options(
                selectinload(GroupInvitation.group)
            )
            .where(GroupInvitation.user_id == user_id)
        )
        
        if status:
            query = query.where(GroupInvitation.status == status)
        else:
            # По умолчанию показываем только pending
            query = query.where(GroupInvitation.status == GroupInvitationStatus.PENDING)
        
        result = await db.execute(query)
        invitations = result.scalars().all()
        logger.info(f"Найдено приглашений: {len(invitations)}")
        
        # Преобразуем в ответы, обрабатывая возможные ошибки
        response_list = []
        for inv in invitations:
            try:
                logger.info(f"Обработка приглашения {inv.id}: group_id={inv.group_id}, status={inv.status}")
                
                # Загружаем группу отдельно, если она не загружена
                if not inv.group:
                    logger.warning(f"Группа не загружена для приглашения {inv.id}, загружаем отдельно")
                    group_result = await db.execute(
                        select(StudentGroup)
                        .where(StudentGroup.id == inv.group_id)
                        .options(
                            selectinload(StudentGroup.members).joinedload(GroupMember.user)
                        )
                    )
                    inv.group = group_result.scalar_one_or_none()
                    if inv.group:
                        logger.info(f"Группа загружена отдельно: id={inv.group.id}, name={inv.group.name}")
                    else:
                        logger.error(f"Группа {inv.group_id} не найдена для приглашения {inv.id}")
                
                # Используем model_validate напрямую, но с обработкой ошибок
                try:
                    response = GroupInvitationResponse.model_validate(inv)
                    response_list.append(response)
                    logger.info(f"Приглашение {inv.id} успешно сериализовано")
                except Exception as validation_error:
                    logger.warning(f"Ошибка при model_validate для приглашения {inv.id}: {validation_error}")
                    # Пробуем создать ответ вручную
                    try:
                        # Создаем базовый ответ без группы
                        response_dict = {
                            "id": inv.id,
                            "group_id": inv.group_id,
                            "user_id": inv.user_id,
                            "inviter_id": inv.inviter_id,
                            "status": inv.status,
                            "created_at": inv.created_at,
                            "updated_at": inv.updated_at,
                            "responded_at": inv.responded_at,
                            "group": None
                        }
                        
                        # Добавляем информацию о группе, если она загружена
                        if inv.group:
                            try:
                                # Создаем упрощенную информацию о группе
                                group_dict = {
                                    "id": inv.group.id,
                                    "name": inv.group.name,
                                    "description": inv.group.description,
                                    "creator_id": inv.group.creator_id,
                                    "created_at": inv.group.created_at,
                                    "updated_at": inv.group.updated_at,
                                    "members": []
                                }
                                response_dict["group"] = group_dict
                            except Exception as group_error:
                                logger.warning(f"Не удалось добавить информацию о группе: {group_error}")
                        
                        response = GroupInvitationResponse.model_validate(response_dict)
                        response_list.append(response)
                        logger.info(f"Приглашение {inv.id} успешно сериализовано (упрощенный метод)")
                    except Exception as fallback_error:
                        logger.error(f"Ошибка при упрощенной сериализации приглашения {inv.id}: {fallback_error}", exc_info=True)
                        # Пропускаем это приглашение
                        continue
            except Exception as e:
                logger.error(f"Ошибка при сериализации приглашения {inv.id}: {e}", exc_info=True)
                # Пропускаем проблемное приглашение, но продолжаем обработку остальных
                continue
        
        logger.info(f"Возвращаем {len(response_list)} приглашений")
        return response_list
    except Exception as e:
        error_str = str(e).lower()
        if "group_invitations" in error_str or "does not exist" in error_str or "relation" in error_str:
            # Таблица еще не создана
            logger.warning(f"Таблица group_invitations еще не создана. Выполните миграцию migrate_groups_invitations.sql. Ошибка: {e}")
            return []
        else:
            logger.error(f"Ошибка при получении приглашений пользователя {user_id}: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Ошибка при получении приглашений: {str(e)}")

@app.post("/groups/invitations/{invitation_id}/accept")
async def accept_group_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Принять приглашение в группу"""
    result = await db.execute(
        select(GroupInvitation)
        .options(selectinload(GroupInvitation.group))
        .where(GroupInvitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    
    if invitation.status != GroupInvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Приглашение уже обработано")
    
    # Проверить, не состоит ли уже в группе
    result = await db.execute(
        select(GroupMember).where(and_(
            GroupMember.group_id == invitation.group_id,
            GroupMember.user_id == invitation.user_id
        ))
    )
    if result.scalar_one_or_none():
        # Удаляем приглашение, если пользователь уже в группе
        await db.delete(invitation)
        await db.commit()
        raise HTTPException(status_code=400, detail="Пользователь уже в группе")
    
    # Добавляем пользователя в группу
    member = GroupMember(
        group_id=invitation.group_id,
        user_id=invitation.user_id
    )
    db.add(member)
    
    # Обновляем статус приглашения
    invitation.status = GroupInvitationStatus.ACCEPTED
    invitation.responded_at = datetime.now()
    
    await db.commit()
    
    # Загружаем member с информацией о пользователе для ответа
    result = await db.execute(
        select(GroupMember)
        .where(GroupMember.id == member.id)
        .options(joinedload(GroupMember.user))
    )
    member = result.scalar_one()
    
    return {
        "success": True,
        "invitation_id": invitation_id,
        "member": GroupMemberResponse.model_validate(member)
    }

@app.post("/groups/invitations/{invitation_id}/reject")
async def reject_group_invitation(
    invitation_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отклонить приглашение в группу (удаляет приглашение)"""
    result = await db.execute(
        select(GroupInvitation).where(GroupInvitation.id == invitation_id)
    )
    invitation = result.scalar_one_or_none()
    
    if not invitation:
        raise HTTPException(status_code=404, detail="Приглашение не найдено")
    
    if invitation.status != GroupInvitationStatus.PENDING:
        raise HTTPException(status_code=400, detail="Приглашение уже обработано")
    
    # Удаляем приглашение (группа исчезнет из списка)
    await db.delete(invitation)
    await db.commit()
    
    return {
        "success": True,
        "invitation_id": invitation_id,
        "message": "Приглашение отклонено"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)

