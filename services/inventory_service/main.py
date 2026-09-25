"""
Inventory Service - Управление предметами и инвентарем
Порт: 8005
"""
from fastapi import FastAPI, Depends, HTTPException, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from services.shared.database import get_db, init_db
from services.shared.models.item import Item, UserItem, ItemRarity, ItemType, TradeRequest, TradeStatus
from services.shared.models.user import User
from services.shared.utils import ServiceClient
from services.shared.realtime import push_user_event
import logging
import random

logger = logging.getLogger(__name__)


async def notify_trade_status_change(
    trade: TradeRequest,
    *,
    payload_extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Отправить событие об изменении статуса обмена обоим участникам."""
    payload: Dict[str, Any] = {
        "trade_id": trade.id,
        "status": trade.status.value if hasattr(trade.status, "value") else str(trade.status),
        "initiator_id": trade.initiator_id,
        "recipient_id": trade.recipient_id,
    }
    if getattr(trade, "comment", None):
        payload["comment"] = trade.comment
    if payload_extra:
        payload.update(payload_extra)

    recipients = {trade.initiator_id, trade.recipient_id}
    for target_user_id in recipients:
        if not target_user_id:
            continue
        try:
            await push_user_event(
                target_user_id,
                "inventory.trade.updated",
                payload=payload,
                metadata={"source": "inventory_service"},
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Не удалось отправить событие обновления обмена пользователю %s: %s", target_user_id, exc)

# Pydantic схемы
class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    rarity: ItemRarity = ItemRarity.COMMON
    type: ItemType = ItemType.CONSUMABLE
    base_price: int = Field(default=0, ge=0)
    reward_coins: int = Field(default=0, ge=0)
    reward_intelligence_points: int = Field(default=0, ge=0)
    reward_satisfaction: int = Field(default=0, ge=0)
    image_filename: Optional[str] = None
    image_data: Optional[str] = None  # Base64 строка

class ItemUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = None
    rarity: Optional[ItemRarity] = None
    type: Optional[ItemType] = None
    base_price: Optional[int] = Field(None, ge=0)
    reward_coins: Optional[int] = Field(None, ge=0)
    reward_intelligence_points: Optional[int] = Field(None, ge=0)
    reward_satisfaction: Optional[int] = Field(None, ge=0)
    image_filename: Optional[str] = None
    image_data: Optional[str] = None  # Base64 строка

class ItemResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    rarity: ItemRarity
    type: ItemType
    base_price: int
    reward_coins: int
    reward_intelligence_points: int
    reward_satisfaction: int
    image_filename: Optional[str]
    image_data: Optional[str]  # Base64 строка (может быть большой)
    
    class Config:
        from_attributes = True

class UserItemResponse(BaseModel):
    id: int
    user_id: int
    item_id: int
    quantity: int
    item: ItemResponse
    
    class Config:
        from_attributes = True

class TradeRequestCreate(BaseModel):
    recipient_id: int
    initiator_item_id: Optional[int] = None
    initiator_quantity: int = Field(default=1, ge=1)
    requested_item_id: Optional[int] = None
    requested_quantity: int = Field(default=1, ge=1)
    comment: Optional[str] = Field(default=None, max_length=500)

class TradeRequestResponse(BaseModel):
    id: int
    initiator_id: int
    recipient_id: int
    initiator_item_id: Optional[int]
    initiator_quantity: int
    requested_item_id: Optional[int]
    requested_quantity: int
    status: TradeStatus
    created_at: datetime
    updated_at: Optional[datetime]
    comment: Optional[str] = None
    # Информация о предметах (опционально, загружается отдельно)
    initiator_item: Optional[ItemResponse] = None
    requested_item: Optional[ItemResponse] = None
    # Информация об инициаторе и получателе
    initiator_username: Optional[str] = None
    recipient_username: Optional[str] = None
    
    class Config:
        from_attributes = True

class LootboxOpenRequest(BaseModel):
    user_id: int

class LootboxOpenResponse(BaseModel):
    success: bool
    item: ItemResponse
    coins_spent: int
    remaining_coins: int

# FastAPI приложение
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path as FilePath

app = FastAPI(title="Inventory Service", version="1.0.0")


async def apply_inventory_migrations():
    """Применить миграции для таблицы trade_requests."""
    from services.shared.database import execute_migration_sql

    migration_sql = """
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='trade_requests' AND column_name='comment'
        ) THEN
            ALTER TABLE trade_requests ADD COLUMN comment TEXT;
        END IF;
    END $$;
    """
    await execute_migration_sql(migration_sql)

# Монтируем static директорию для изображений
static_dir = FilePath("/app/static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

@app.on_event("startup")
async def startup():
    await init_db()
    await apply_inventory_migrations()

@app.get("/")
async def root():
    return {"service": "Inventory Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/items/image/{filename}")
async def get_item_image(filename: str):
    """Получить изображение предмета"""
    image_path = FilePath(f"/app/static/items/{filename}")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Изображение не найдено")
    return FileResponse(image_path)

# CRUD предметов (Items)
# ВАЖНО: Роут для добавления предметов в инвентарь должен быть объявлен ПЕРЕД /items/{item_id}
# чтобы избежать конфликта при сопоставлении путей в FastAPI
@app.post("/items/add-to-user/{user_id}")
async def add_item_to_inventory(
    user_id: int,
    item_id: int = Query(..., description="ID предмета"),
    quantity: int = Query(1, description="Количество"),
    db: AsyncSession = Depends(get_db)
):
    """Добавить предмет в инвентарь пользователя"""
    # Убрана проверка существования пользователя - микросервисы должны быть слабо связаны
    # Проверка существования должна происходить в user_service
    # Inventory-service доверяет данным от других сервисов
    
    # Проверка существования предмета
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    
    # Проверить, есть ли уже этот предмет у пользователя
    result = await db.execute(
        select(UserItem).where(and_(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id
        ))
    )
    user_item = result.scalar_one_or_none()
    
    if user_item:
        # Увеличить количество
        user_item.quantity += quantity
    else:
        # Создать новую запись
        user_item = UserItem(user_id=user_id, item_id=item_id, quantity=quantity)
        db.add(user_item)
    
    await db.commit()
    await db.refresh(user_item)
    
    return {
        "user_id": user_id,
        "item_id": item_id,
        "item_name": item.name,
        "quantity": user_item.quantity,
        "added": quantity
    }

# CRUD предметов (Items) - остальные роуты
@app.post("/items/", response_model=ItemResponse, status_code=201)
async def create_item(item_in: ItemCreate, db: AsyncSession = Depends(get_db)):
    """Создать новый предмет"""
    # Проверка уникальности имени
    result = await db.execute(select(Item).where(Item.name == item_in.name))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Предмет с таким именем уже существует")
    
    # Pydantic already converts strings to enum instances, so use directly
    item = Item(
        name=item_in.name,
        description=item_in.description,
        rarity=item_in.rarity,  # Already ItemRarity instance
        type=item_in.type,  # Already ItemType instance
        base_price=item_in.base_price,
        reward_coins=item_in.reward_coins,
        reward_intelligence_points=item_in.reward_intelligence_points,
        reward_satisfaction=item_in.reward_satisfaction,
        image_filename=item_in.image_filename,
        image_data=item_in.image_data,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item

@app.get("/items/", response_model=List[ItemResponse])
async def list_items(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Список всех предметов"""
    result = await db.execute(select(Item).offset(skip).limit(limit))
    return result.scalars().all()

@app.get("/items/{item_id}", response_model=ItemResponse)
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Получить предмет по ID"""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    return item

@app.get("/items/rarity/{rarity}", response_model=List[ItemResponse])
async def get_items_by_rarity(rarity: ItemRarity, db: AsyncSession = Depends(get_db)):
    """Получить предметы по редкости"""
    result = await db.execute(select(Item).where(Item.rarity == rarity))
    return result.scalars().all()

@app.get("/items/type/{item_type}", response_model=List[ItemResponse])
async def get_items_by_type(item_type: ItemType, db: AsyncSession = Depends(get_db)):
    """Получить предметы по типу"""
    result = await db.execute(select(Item).where(Item.type == item_type))
    return result.scalars().all()

@app.put("/items/{item_id}", response_model=ItemResponse)
async def update_item(
    item_id: int,
    item_in: ItemUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить предмет"""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    
    update_data = item_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    await db.commit()
    await db.refresh(item)
    return item

@app.delete("/items/{item_id}", response_model=ItemResponse)
async def delete_item(item_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить предмет"""
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Предмет не найден")
    
    await db.delete(item)
    return item

# Остальные роуты инвентаря пользователя
@app.post("/inventory/users/{user_id}/items/{item_id}/use")
async def use_inventory_item(
    user_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Использовать предмет и выдать награды пользователю"""
    result = await db.execute(
        select(UserItem).where(and_(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id
        ))
    )
    user_item = result.scalar_one_or_none()

    if not user_item or user_item.quantity <= 0:
        raise HTTPException(status_code=404, detail="Предмет не найден в инвентаре или недоступен")

    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Предмет не найден")

    rewards = {
        "coins": item.reward_coins or 0,
        "intelligence_points": item.reward_intelligence_points or 0,
        "satisfaction": item.reward_satisfaction or 0
    }

    remaining_quantity = user_item.quantity - 1
    if remaining_quantity < 0:
        raise HTTPException(status_code=400, detail="Недостаточно предметов для использования")

    user_client = ServiceClient("user") if rewards["coins"] > 0 else None
    character_client = ServiceClient("character") if (rewards["intelligence_points"] > 0 or rewards["satisfaction"] > 0) else None

    try:
        # Выдать монеты пользователю
        if rewards["coins"] > 0 and user_client:
            await user_client.post(f"/users/{user_id}/coins/add", json={"amount": rewards["coins"]})

        character_id = None
        if character_client:
            character_data = await character_client.get(f"/characters/user/{user_id}")
            character_id = character_data.get("id")
            if not character_id:
                raise HTTPException(status_code=500, detail="Персонаж пользователя не найден")

            if rewards["satisfaction"] > 0:
                await character_client.post(
                    f"/characters/{character_id}/satisfaction/adjust",
                    params={"amount": rewards["satisfaction"]}
                )
            if rewards["intelligence_points"] > 0:
                await character_client.post(
                    f"/characters/{character_id}/intelligence/add",
                    json={"points": rewards["intelligence_points"]}
                )

        if remaining_quantity == 0:
            await db.delete(user_item)
        else:
            user_item.quantity = remaining_quantity

        await db.commit()
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Ошибка при использовании предмета: %s", e)
        raise HTTPException(status_code=502, detail="Не удалось использовать предмет")
    finally:
        if user_client:
            await user_client.close()
        if character_client:
            await character_client.close()

    return {
        "success": True,
        "item_id": item_id,
        "rewards": rewards,
        "remaining_quantity": max(remaining_quantity, 0)
    }


@app.post("/inventory/users/{user_id}/items/remove")
async def remove_item_from_inventory(
    user_id: int,
    item_id: int = Query(..., description="ID предмета"),
    quantity: int = Query(1, description="Количество"),
    db: AsyncSession = Depends(get_db)
):
    """Удалить/уменьшить количество предмета в инвентаре"""
    result = await db.execute(
        select(UserItem).where(and_(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id
        ))
    )
    user_item = result.scalar_one_or_none()
    
    if not user_item:
        raise HTTPException(status_code=404, detail="Предмет не найден в инвентаре")
    
    if user_item.quantity < quantity:
        raise HTTPException(status_code=400, detail="Недостаточно предметов")
    
    user_item.quantity -= quantity
    
    if user_item.quantity == 0:
        # Удалить запись, если количество стало 0
        await db.delete(user_item)
        remaining = 0
    else:
        await db.commit()
        await db.refresh(user_item)
        remaining = user_item.quantity
    
    return {
        "user_id": user_id,
        "item_id": item_id,
        "removed": quantity,
        "remaining": remaining
    }

@app.post("/inventory/users/{user_id}/items/transfer")
async def transfer_item(
    user_id: int,
    target_user_id: int = Query(..., description="ID получателя"),
    item_id: int = Query(..., description="ID предмета"),
    quantity: int = Query(1, description="Количество"),
    db: AsyncSession = Depends(get_db)
):
    """Передать предмет другому пользователю"""
    # Проверка существования обоих пользователей
    result = await db.execute(select(User).where(User.id == user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Отправитель не найден")
    
    result = await db.execute(select(User).where(User.id == target_user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Получатель не найден")
    
    # Удалить у отправителя
    result = await db.execute(
        select(UserItem).where(and_(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id
        ))
    )
    sender_item = result.scalar_one_or_none()
    
    if not sender_item:
        raise HTTPException(status_code=404, detail="Предмет не найден у отправителя")
    
    if sender_item.quantity < quantity:
        raise HTTPException(status_code=400, detail="Недостаточно предметов для передачи")
    
    sender_item.quantity -= quantity
    if sender_item.quantity == 0:
        await db.delete(sender_item)
    
    # Добавить получателю
    result = await db.execute(
        select(UserItem).where(and_(
            UserItem.user_id == target_user_id,
            UserItem.item_id == item_id
        ))
    )
    receiver_item = result.scalar_one_or_none()
    
    if receiver_item:
        receiver_item.quantity += quantity
    else:
        receiver_item = UserItem(
            user_id=target_user_id,
            item_id=item_id,
            quantity=quantity
        )
        db.add(receiver_item)
    
    # Получить информацию о предмете для уведомления
    result = await db.execute(select(Item).where(Item.id == item_id))
    item = result.scalar_one_or_none()
    item_name = item.name if item else f"Предмет #{item_id}"
    
    # Получить информацию о пользователях для уведомления (до commit)
    result = await db.execute(select(User).where(User.id == user_id))
    sender = result.scalar_one_or_none()
    sender_username = sender.username if sender else f"User #{user_id}"
    
    result = await db.execute(select(User).where(User.id == target_user_id))
    receiver = result.scalar_one_or_none()
    receiver_username = receiver.username if receiver else f"User #{target_user_id}"
    
    await db.commit()
    
    # Логируем обмен для уведомлений (в будущем можно добавить сервис уведомлений)
    logger.info(f"Обмен предметов: Пользователь {sender_username} (ID: {user_id}) передал {quantity}x {item_name} пользователю {receiver_username} (ID: {target_user_id})")
    
    return {
        "from_user_id": user_id,
        "to_user_id": target_user_id,
        "item_id": item_id,
        "item_name": item_name,
        "quantity": quantity,
        "success": True,
        "message": f"Предмет '{item_name}' успешно передан пользователю {receiver_username}"
    }

@app.get("/inventory/users/{user_id}/items/{item_id}/check")
async def check_item_availability(
    user_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Проверить наличие предмета у пользователя"""
    result = await db.execute(
        select(UserItem).where(and_(
            UserItem.user_id == user_id,
            UserItem.item_id == item_id
        ))
    )
    user_item = result.scalar_one_or_none()
    
    if not user_item:
        return {
            "user_id": user_id,
            "item_id": item_id,
            "has_item": False,
            "quantity": 0
        }
    
    return {
        "user_id": user_id,
        "item_id": item_id,
        "has_item": True,
        "quantity": user_item.quantity
    }

# ===== ОБМЕН ПРЕДМЕТАМИ =====

async def enrich_trade_request_with_items(trade: TradeRequest, db: AsyncSession) -> TradeRequestResponse:
    """Обогащает TradeRequest информацией о предметах и пользователях"""
    trade_dict = {
        "id": trade.id,
        "initiator_id": trade.initiator_id,
        "recipient_id": trade.recipient_id,
        "initiator_item_id": trade.initiator_item_id,
        "initiator_quantity": trade.initiator_quantity,
        "requested_item_id": trade.requested_item_id,
        "requested_quantity": trade.requested_quantity,
        "status": trade.status,
        "created_at": trade.created_at,
        "updated_at": trade.updated_at,
        "comment": trade.comment,
        "initiator_item": None,
        "requested_item": None,
        "initiator_username": None,
        "recipient_username": None
    }
    
    # Загружаем информацию о предмете инициатора
    if trade.initiator_item_id:
        item_result = await db.execute(select(Item).where(Item.id == trade.initiator_item_id))
        initiator_item = item_result.scalar_one_or_none()
        if initiator_item:
            trade_dict["initiator_item"] = ItemResponse.model_validate(initiator_item)
    
    # Загружаем информацию о запрашиваемом предмете
    if trade.requested_item_id:
        item_result = await db.execute(select(Item).where(Item.id == trade.requested_item_id))
        requested_item = item_result.scalar_one_or_none()
        if requested_item:
            trade_dict["requested_item"] = ItemResponse.model_validate(requested_item)
    
    # Загружаем информацию об инициаторе
    user_result = await db.execute(select(User).where(User.id == trade.initiator_id))
    initiator = user_result.scalar_one_or_none()
    if initiator:
        trade_dict["initiator_username"] = initiator.username
    
    # Загружаем информацию о получателе
    user_result = await db.execute(select(User).where(User.id == trade.recipient_id))
    recipient = user_result.scalar_one_or_none()
    if recipient:
        trade_dict["recipient_username"] = recipient.username
    
    return TradeRequestResponse(**trade_dict)

@app.post("/trades/", response_model=TradeRequestResponse, status_code=201)
async def create_trade_request(
    trade_in: TradeRequestCreate,
    initiator_id: int = Query(..., description="ID инициатора обмена"),
    db: AsyncSession = Depends(get_db)
):
    """Создать запрос на обмен"""
    # Проверка существования получателя
    result = await db.execute(select(User).where(User.id == trade_in.recipient_id))
    recipient = result.scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=404, detail="Получатель не найден")
    
    if trade_in.recipient_id == initiator_id:
        raise HTTPException(status_code=400, detail="Нельзя обмениваться с самим собой")
    
    comment_value = (trade_in.comment or "").strip()
    if comment_value == "":
        comment_value = None

    # Создаем запрос на обмен сначала (нужен ID для резервирования)
    trade_request = TradeRequest(
        initiator_id=initiator_id,
        recipient_id=trade_in.recipient_id,
        initiator_item_id=trade_in.initiator_item_id,
        initiator_quantity=trade_in.initiator_quantity,
        requested_item_id=trade_in.requested_item_id,
        requested_quantity=trade_in.requested_quantity,
        status=TradeStatus.PENDING,
        comment=comment_value
    )
    db.add(trade_request)
    await db.flush()  # Получаем ID без коммита
    
    # Проверка наличия предмета у инициатора и резервирование (если указан)
    if trade_in.initiator_item_id:
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == initiator_id,
                UserItem.item_id == trade_in.initiator_item_id,
                # Исключаем уже зарезервированные предметы
                (UserItem.reserved_for_trade_id.is_(None) | (UserItem.reserved_for_trade_id == trade_request.id))
            ))
        )
        initiator_item = result.scalar_one_or_none()
        if not initiator_item or initiator_item.quantity < trade_in.initiator_quantity:
            await db.rollback()
            raise HTTPException(status_code=400, detail="Недостаточно предметов для обмена (возможно, предмет уже зарезервирован)")
        
        # Резервируем предмет вместо удаления
        if initiator_item.quantity == trade_in.initiator_quantity:
            # Если количество совпадает - просто резервируем всю запись
            initiator_item.reserved_for_trade_id = trade_request.id
        else:
            # Если количество больше - создаем отдельную запись для резервирования
            reserved_item = UserItem(
                user_id=initiator_id,
                item_id=trade_in.initiator_item_id,
                quantity=trade_in.initiator_quantity,
                reserved_for_trade_id=trade_request.id
            )
            db.add(reserved_item)
            initiator_item.quantity -= trade_in.initiator_quantity
    
    # Проверка наличия запрашиваемого предмета у получателя (если указан)
    if trade_in.requested_item_id:
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade_in.recipient_id,
                UserItem.item_id == trade_in.requested_item_id,
                # Исключаем зарезервированные предметы
                UserItem.reserved_for_trade_id.is_(None)
            ))
        )
        recipient_item = result.scalar_one_or_none()
        if not recipient_item or recipient_item.quantity < trade_in.requested_quantity:
            await db.rollback()
            raise HTTPException(status_code=400, detail="У получателя нет запрашиваемого предмета (возможно, предмет зарезервирован)")
    
    await db.commit()
    await db.refresh(trade_request)
    
    initiator_username = None
    initiator_item_name = None
    requested_item_name = None
    # Отправляем уведомление получателю
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == initiator_id))
        initiator = result.scalar_one_or_none()
        initiator_username = initiator.username if initiator else None
        
        # Получаем информацию о предметах
        if trade_request.initiator_item_id:
            result = await db.execute(select(Item).where(Item.id == trade_request.initiator_item_id))
            item = result.scalar_one_or_none()
            initiator_item_name = item.name if item else None
        if trade_request.requested_item_id:
            result = await db.execute(select(Item).where(Item.id == trade_request.requested_item_id))
            item = result.scalar_one_or_none()
            requested_item_name = item.name if item else None
        
        await bot_service.post(
            "/notifications/trade-request",
            json={
                "recipient_user_id": trade_in.recipient_id,
                "initiator_user_id": initiator_id,
                "trade_id": trade_request.id,
                "initiator_username": initiator_username,
                "initiator_item_name": initiator_item_name,
                "requested_item_name": requested_item_name,
                "initiator_quantity": trade_in.initiator_quantity,
                "requested_quantity": trade_in.requested_quantity,
                "comment": comment_value,
            },
        )
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о предложении обмена: {e}")
    
    await push_user_event(
        trade_in.recipient_id,
        "inventory.trade.received",
        payload={
            "trade_id": trade_request.id,
            "initiator_user_id": initiator_id,
            "initiator_username": initiator_username,
            "initiator_item_id": trade_request.initiator_item_id,
            "initiator_item_name": initiator_item_name,
            "initiator_quantity": trade_in.initiator_quantity,
            "requested_item_id": trade_request.requested_item_id,
            "requested_item_name": requested_item_name,
            "requested_quantity": trade_in.requested_quantity,
            "comment": comment_value,
        },
        metadata={"source": "inventory_service"},
    )
    
    # Возвращаем обогащенный ответ с информацией о предметах
    return await enrich_trade_request_with_items(trade_request, db)

@app.get("/trades/users/{user_id}/received", response_model=List[TradeRequestResponse])
async def get_received_trade_requests(
    user_id: int,
    status: Optional[TradeStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить запросы на обмен, полученные пользователем"""
    query = select(TradeRequest).where(TradeRequest.recipient_id == user_id)
    if status:
        query = query.where(TradeRequest.status == status)
    else:
        query = query.where(TradeRequest.status == TradeStatus.PENDING)
    
    result = await db.execute(query.order_by(TradeRequest.created_at.desc()))
    trade_requests = result.scalars().all()
    
    # Загружаем информацию о предметах и пользователях
    trade_responses = []
    for trade in trade_requests:
        trade_dict = {
            "id": trade.id,
            "initiator_id": trade.initiator_id,
            "recipient_id": trade.recipient_id,
            "initiator_item_id": trade.initiator_item_id,
            "initiator_quantity": trade.initiator_quantity,
            "requested_item_id": trade.requested_item_id,
            "requested_quantity": trade.requested_quantity,
            "status": trade.status,
            "created_at": trade.created_at,
            "updated_at": trade.updated_at,
            "comment": trade.comment,
            "initiator_item": None,
            "requested_item": None,
            "initiator_username": None,
            "recipient_username": None
        }
        
        # Загружаем информацию о предмете инициатора
        if trade.initiator_item_id:
            item_result = await db.execute(select(Item).where(Item.id == trade.initiator_item_id))
            initiator_item = item_result.scalar_one_or_none()
            if initiator_item:
                trade_dict["initiator_item"] = ItemResponse.model_validate(initiator_item)
        
        # Загружаем информацию о запрашиваемом предмете
        if trade.requested_item_id:
            item_result = await db.execute(select(Item).where(Item.id == trade.requested_item_id))
            requested_item = item_result.scalar_one_or_none()
            if requested_item:
                trade_dict["requested_item"] = ItemResponse.model_validate(requested_item)
        
        # Загружаем информацию об инициаторе
        user_result = await db.execute(select(User).where(User.id == trade.initiator_id))
        initiator = user_result.scalar_one_or_none()
        if initiator:
            trade_dict["initiator_username"] = initiator.username
        
        # Загружаем информацию о получателе
        user_result = await db.execute(select(User).where(User.id == trade.recipient_id))
        recipient = user_result.scalar_one_or_none()
        if recipient:
            trade_dict["recipient_username"] = recipient.username
        
        trade_responses.append(TradeRequestResponse(**trade_dict))
    
    return trade_responses

@app.get("/trades/users/{user_id}/sent", response_model=List[TradeRequestResponse])
async def get_sent_trade_requests(
    user_id: int,
    status: Optional[TradeStatus] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить запросы на обмен, отправленные пользователем"""
    query = select(TradeRequest).where(TradeRequest.initiator_id == user_id)
    if status:
        query = query.where(TradeRequest.status == status)
    
    result = await db.execute(query.order_by(TradeRequest.created_at.desc()))
    trade_requests = result.scalars().all()
    
    # Загружаем информацию о предметах
    trade_responses = []
    for trade in trade_requests:
        trade_responses.append(await enrich_trade_request_with_items(trade, db))
    
    return trade_responses

@app.post("/trades/{trade_id}/accept", response_model=TradeRequestResponse)
async def accept_trade_request(
    trade_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Принять запрос на обмен"""
    result = await db.execute(select(TradeRequest).where(TradeRequest.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Запрос на обмен не найден")
    
    if trade.status != TradeStatus.PENDING:
        raise HTTPException(status_code=400, detail="Запрос уже обработан")
    
    # Выполняем обмен
    # 1. Передаем предмет от инициатора получателю (если есть)
    if trade.initiator_item_id:
        # Находим зарезервированный предмет
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade.initiator_id,
                UserItem.item_id == trade.initiator_item_id,
                UserItem.reserved_for_trade_id == trade.id
            ))
        )
        reserved_item = result.scalar_one_or_none()
        
        if not reserved_item:
            raise HTTPException(status_code=400, detail="Зарезервированный предмет не найден")
        
        # Меняем владельца зарезервированного предмета
        reserved_item.user_id = trade.recipient_id
        reserved_item.reserved_for_trade_id = None  # Снимаем резервирование
        
        # Проверяем, есть ли уже такой предмет у получателя
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade.recipient_id,
                UserItem.item_id == trade.initiator_item_id,
                UserItem.reserved_for_trade_id.is_(None)
            ))
        )
        existing_item = result.scalar_one_or_none()
        
        if existing_item and existing_item.id != reserved_item.id:
            # Если у получателя уже есть такой предмет - объединяем
            existing_item.quantity += reserved_item.quantity
            await db.delete(reserved_item)
    
    # 2. Передаем предмет от получателя инициатору (если есть)
    if trade.requested_item_id:
        # Уменьшаем количество у получателя (исключаем зарезервированные)
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade.recipient_id,
                UserItem.item_id == trade.requested_item_id,
                UserItem.reserved_for_trade_id.is_(None)  # Исключаем зарезервированные
            ))
        )
        recipient_item = result.scalar_one_or_none()
        if not recipient_item or recipient_item.quantity < trade.requested_quantity:
            raise HTTPException(status_code=400, detail="У получателя недостаточно предметов (возможно, предмет зарезервирован)")
        
        recipient_item.quantity -= trade.requested_quantity
        if recipient_item.quantity == 0:
            await db.delete(recipient_item)
        
        # Увеличиваем количество у инициатора
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade.initiator_id,
                UserItem.item_id == trade.requested_item_id,
                UserItem.reserved_for_trade_id.is_(None)  # Исключаем зарезервированные
            ))
        )
        initiator_item = result.scalar_one_or_none()
        if initiator_item:
            initiator_item.quantity += trade.requested_quantity
        else:
            initiator_item = UserItem(
                user_id=trade.initiator_id,
                item_id=trade.requested_item_id,
                quantity=trade.requested_quantity
            )
            db.add(initiator_item)
    
    # Обновляем статус запроса
    trade.status = TradeStatus.ACCEPTED
    await db.commit()
    await db.refresh(trade)
    
    # Возвращаем обогащенный ответ с информацией о предметах
    enriched_trade = await enrich_trade_request_with_items(trade, db)
    
    # Отправляем уведомление инициатору о принятии обмена
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == trade.recipient_id))
        acceptor = result.scalar_one_or_none()
        acceptor_username = acceptor.username if acceptor else None
        await bot_service.post("/notifications/trade-request-accepted", json={
            "initiator_user_id": trade.initiator_id,
            "acceptor_username": acceptor_username
        })
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление о принятии обмена: {e}")
    
    await notify_trade_status_change(trade)
    
    return enriched_trade

@app.post("/trades/{trade_id}/reject", response_model=TradeRequestResponse)
async def reject_trade_request(
    trade_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отклонить запрос на обмен"""
    result = await db.execute(select(TradeRequest).where(TradeRequest.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Запрос на обмен не найден")
    
    if trade.status != TradeStatus.PENDING:
        raise HTTPException(status_code=400, detail="Запрос уже обработан")
    
    trade.status = TradeStatus.REJECTED
    
    # Возвращаем зарезервированный предмет инициатору
    if trade.initiator_item_id:
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade.initiator_id,
                UserItem.item_id == trade.initiator_item_id,
                UserItem.reserved_for_trade_id == trade.id
            ))
        )
        reserved_item = result.scalar_one_or_none()
        
        if reserved_item:
            # Если это отдельная запись для резервирования - объединяем с основной
            result = await db.execute(
                select(UserItem).where(and_(
                    UserItem.user_id == trade.initiator_id,
                    UserItem.item_id == trade.initiator_item_id,
                    UserItem.reserved_for_trade_id.is_(None),
                    UserItem.id != reserved_item.id
                ))
            )
            existing_item = result.scalar_one_or_none()
            
            if existing_item:
                existing_item.quantity += reserved_item.quantity
                await db.delete(reserved_item)
            else:
                # Если основной записи нет - просто снимаем резервирование
                reserved_item.reserved_for_trade_id = None
    
    await db.commit()
    await db.refresh(trade)
    
    # Возвращаем обогащенный ответ с информацией о предметах
    enriched_trade = await enrich_trade_request_with_items(trade, db)
    
    # Отправляем уведомление инициатору об отклонении обмена
    try:
        bot_service = ServiceClient("max_bot")
        result = await db.execute(select(User).where(User.id == trade.recipient_id))
        rejector = result.scalar_one_or_none()
        rejector_username = rejector.username if rejector else None
        await bot_service.post("/notifications/trade-request-rejected", json={
            "initiator_user_id": trade.initiator_id,
            "rejector_username": rejector_username
        })
        await bot_service.close()
    except Exception as e:
        logger.warning(f"Не удалось отправить уведомление об отклонении обмена: {e}")
    
    await notify_trade_status_change(trade)
    
    return enriched_trade

@app.delete("/trades/{trade_id}")
async def cancel_trade_request(
    trade_id: int,
    user_id: int = Query(..., description="ID пользователя, отменяющего запрос"),
    db: AsyncSession = Depends(get_db)
):
    """Отменить запрос на обмен (только инициатор может отменить)"""
    result = await db.execute(select(TradeRequest).where(TradeRequest.id == trade_id))
    trade = result.scalar_one_or_none()
    if not trade:
        raise HTTPException(status_code=404, detail="Запрос на обмен не найден")
    
    if trade.initiator_id != user_id:
        raise HTTPException(status_code=403, detail="Только инициатор может отменить запрос")
    
    if trade.status != TradeStatus.PENDING:
        raise HTTPException(status_code=400, detail="Нельзя отменить обработанный запрос")
    
    trade.status = TradeStatus.CANCELLED
    
    # Возвращаем зарезервированный предмет инициатору
    if trade.initiator_item_id:
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == trade.initiator_id,
                UserItem.item_id == trade.initiator_item_id,
                UserItem.reserved_for_trade_id == trade.id
            ))
        )
        reserved_item = result.scalar_one_or_none()
        
        if reserved_item:
            # Если это отдельная запись для резервирования - объединяем с основной
            result = await db.execute(
                select(UserItem).where(and_(
                    UserItem.user_id == trade.initiator_id,
                    UserItem.item_id == trade.initiator_item_id,
                    UserItem.reserved_for_trade_id.is_(None),
                    UserItem.id != reserved_item.id
                ))
            )
            existing_item = result.scalar_one_or_none()
            
            if existing_item:
                existing_item.quantity += reserved_item.quantity
                await db.delete(reserved_item)
            else:
                # Если основной записи нет - просто снимаем резервирование
                reserved_item.reserved_for_trade_id = None
    
    await db.commit()
    await db.refresh(trade)
    
    await notify_trade_status_change(trade)
    
    return {"success": True, "trade_id": trade_id}

@app.get("/trades/users/{user_id}/inventory/{target_user_id}")
async def get_user_inventory_for_trade(
    user_id: int = Path(..., description="ID пользователя, запрашивающего инвентарь"),
    target_user_id: int = Path(..., description="ID пользователя, чей инвентарь нужно просмотреть"),
    db: AsyncSession = Depends(get_db)
):
    """Получить инвентарь пользователя для просмотра при создании запроса на обмен"""
    # Проверка существования пользователя
    result = await db.execute(select(User).where(User.id == target_user_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Получаем предметы пользователя
    result = await db.execute(
        select(UserItem, Item)
        .join(Item, UserItem.item_id == Item.id)
        .where(UserItem.user_id == target_user_id)
    )
    items = result.all()
    
    return [
        {
            "item_id": item.Item.id,
            "item_name": item.Item.name,
            "item_description": item.Item.description,
            "item_rarity": item.Item.rarity.value,
            "quantity": item.UserItem.quantity
        }
        for item in items
    ]

@app.get("/inventory/users/{user_id}", response_model=List[UserItemResponse])
async def get_user_inventory(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Получить инвентарь пользователя (исключая зарезервированные предметы)"""
    result = await db.execute(
        select(UserItem)
        .where(and_(
            UserItem.user_id == user_id,
            UserItem.reserved_for_trade_id.is_(None)  # Исключаем зарезервированные предметы
        ))
        .offset(skip)
        .limit(limit)
    )
    user_items = result.scalars().all()
    
    # Загрузить информацию о предметах
    response = []
    for user_item in user_items:
        item_result = await db.execute(select(Item).where(Item.id == user_item.item_id))
        item = item_result.scalar_one_or_none()
        if item:
            response.append(UserItemResponse(
                id=user_item.id,
                user_id=user_item.user_id,
                item_id=user_item.item_id,
                quantity=user_item.quantity,
                item=ItemResponse.model_validate(item)
            ))
    
    return response

# Лутбокс
LOOTBOX_COST = 10
RARITY_WEIGHTS = {
    ItemRarity.COMMON: 50,      # 50%
    ItemRarity.UNCOMMON: 25,    # 25%
    ItemRarity.RARE: 15,        # 15%
    ItemRarity.EPIC: 7,         # 7%
    ItemRarity.LEGENDARY: 3     # 3%
}

def calculate_lootbox_item(items: List[Item]) -> Optional[Item]:
    """
    Рассчитать выпавший предмет на основе весов редкости
    """
    if not items:
        return None
    
    # Создаем список предметов с весами
    weighted_items = []
    for item in items:
        weight = RARITY_WEIGHTS.get(item.rarity, 0)
        if weight > 0:
            weighted_items.extend([item] * weight)
    
    if not weighted_items:
        return None
    
    # Случайный выбор предмета
    return random.choice(weighted_items)

@app.post("/inventory/lootbox/open", response_model=LootboxOpenResponse)
async def open_lootbox(
    request: LootboxOpenRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Открыть лутбокс за 50 монет
    """
    user_id = request.user_id
    
    # Проверка баланса монет
    user_service = ServiceClient("user")
    try:
        user_data = await user_service.get(f"/users/{user_id}/coins")
        user_coins = user_data.get("coins", 0) if isinstance(user_data, dict) else 0
        
        if user_coins < LOOTBOX_COST:
            raise HTTPException(
                status_code=400,
                detail=f"Недостаточно монет. Требуется: {LOOTBOX_COST}, доступно: {user_coins}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Ошибка при проверке баланса монет: %s", e)
        raise HTTPException(status_code=500, detail="Не удалось проверить баланс монет")
    finally:
        await user_service.close()
    
    # Получить все предметы из БД
    result = await db.execute(select(Item))
    all_items = result.scalars().all()
    
    if not all_items:
        raise HTTPException(status_code=404, detail="В базе данных нет предметов")
    
    # Рассчитать выпавший предмет
    selected_item = calculate_lootbox_item(list(all_items))
    
    if not selected_item:
        raise HTTPException(status_code=500, detail="Не удалось рассчитать предмет")
    
    # Списать монеты
    user_service = ServiceClient("user")
    try:
        await user_service.post(
            f"/users/{user_id}/coins/subtract",
            json={"amount": LOOTBOX_COST}
        )
        
        # Получить обновленный баланс
        user_data = await user_service.get(f"/users/{user_id}/coins")
        remaining_coins = user_data.get("coins", 0) if isinstance(user_data, dict) else 0
    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Ошибка при списании монет: %s", e)
        raise HTTPException(status_code=500, detail="Не удалось списать монеты")
    finally:
        await user_service.close()
    
    # Добавить предмет в инвентарь
    try:
        result = await db.execute(
            select(UserItem).where(and_(
                UserItem.user_id == user_id,
                UserItem.item_id == selected_item.id
            ))
        )
        user_item = result.scalar_one_or_none()
        
        if user_item:
            user_item.quantity += 1
        else:
            user_item = UserItem(user_id=user_id, item_id=selected_item.id, quantity=1)
            db.add(user_item)
        
        await db.commit()
        await db.refresh(user_item)
    except Exception as e:
        await db.rollback()
        logger.exception("Ошибка при добавлении предмета в инвентарь: %s", e)
        raise HTTPException(status_code=500, detail="Не удалось добавить предмет в инвентарь")
    
    return LootboxOpenResponse(
        success=True,
        item=ItemResponse.model_validate(selected_item),
        coins_spent=LOOTBOX_COST,
        remaining_coins=remaining_coins
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)

