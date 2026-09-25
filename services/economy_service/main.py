"""
Economy Service - Управление магазином и транзакциями
Порт: 8009
"""
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_
from typing import List, Optional
from pydantic import BaseModel, Field

from services.shared.database import get_db, init_db
from services.shared.models.economy import ShopListing, Transaction, TransactionType
from services.shared.models.item import Item
from services.shared.models.user import User
from services.shared.models.character import Character
from services.shared.utils import ServiceClient
import logging

logger = logging.getLogger(__name__)

# Pydantic схемы
class ShopListingCreate(BaseModel):
    seller_id: Optional[int] = None  # ID продавца (None для администраторских товаров)
    item_id: int
    price: int = Field(..., ge=0)
    stock: Optional[int] = Field(None, ge=0)
    is_active: bool = True

class ShopListingUpdate(BaseModel):
    price: Optional[int] = Field(None, ge=0)
    stock: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None

class ShopListingResponse(BaseModel):
    id: int
    seller_id: Optional[int] = None  # Опционально для обратной совместимости со старыми записями
    item_id: int
    price: int
    stock: Optional[int]
    is_active: bool
    
    class Config:
        from_attributes = True

class TransactionResponse(BaseModel):
    id: int
    user_id: int
    type: TransactionType
    amount: int
    description: Optional[str]
    related_item_id: Optional[int]
    related_user_id: Optional[int]
    
    class Config:
        from_attributes = True

class PurchaseRequest(BaseModel):
    user_id: int
    quantity: int = Field(default=1, ge=1)

# FastAPI приложение
app = FastAPI(title="Economy Service", version="1.0.0")

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/")
async def root():
    return {"service": "Economy Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# Магазин
@app.post("/shop/listings/", response_model=ShopListingResponse, status_code=201)
async def create_shop_listing(
    listing_in: ShopListingCreate,
    db: AsyncSession = Depends(get_db)
):
    """Создать товар в магазине (предмет удаляется из инвентаря продавца, если указан seller_id)"""
    # Проверка существования предмета
    result = await db.execute(select(Item).where(Item.id == listing_in.item_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Предмет не найден")
    
    # Проверка существования продавца (если указан)
    if listing_in.seller_id is not None:
        result = await db.execute(select(User).where(User.id == listing_in.seller_id))
        seller = result.scalar_one_or_none()
        if not seller:
            raise HTTPException(status_code=404, detail="Продавец не найден")
        
        # Проверка наличия предмета у продавца и удаление из инвентаря
        quantity_to_list = listing_in.stock if listing_in.stock is not None else 1
        inventory_service = ServiceClient("inventory")
        try:
            # Получаем инвентарь продавца
            inventory = await inventory_service.get(f"/inventory/users/{listing_in.seller_id}")
            user_item = next((item for item in inventory if item.get("item_id") == listing_in.item_id), None)
            
            if not user_item:
                raise HTTPException(status_code=400, detail="У вас нет этого предмета")
            
            if user_item.get("quantity", 0) < quantity_to_list:
                raise HTTPException(status_code=400, detail=f"Недостаточно предметов. У вас: {user_item.get('quantity', 0)}, требуется: {quantity_to_list}")
            
            # Удаляем предмет из инвентаря продавца
            await inventory_service.post(
                f"/inventory/users/{listing_in.seller_id}/items/remove",
                params={"item_id": listing_in.item_id, "quantity": quantity_to_list}
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка при работе с инвентарём: {str(e)}")
        finally:
            await inventory_service.close()
    # Если seller_id None (администраторский товар), предмет не удаляется из инвентаря
    
    # Создаём листинг
    listing = ShopListing(**listing_in.model_dump())
    db.add(listing)
    await db.commit()
    await db.refresh(listing)
    return listing

@app.get("/shop/listings/", response_model=List[ShopListingResponse])
async def list_shop_listings(
    skip: int = 0,
    limit: int = 100,
    active_only: bool = True,
    db: AsyncSession = Depends(get_db)
):
    """Список товаров в магазине"""
    from sqlalchemy import text
    
    # Проверяем существование колонки seller_id через информационную схему
    check_column_sql = text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'shop_listings' AND column_name = 'seller_id'
    """)
    result = await db.execute(check_column_sql)
    has_seller_id = result.fetchone() is not None
    
    # Если колонки нет, пытаемся добавить
    if not has_seller_id:
        try:
            await db.execute(text("ALTER TABLE shop_listings ADD COLUMN seller_id INTEGER REFERENCES users(id) ON DELETE CASCADE"))
            await db.commit()
            has_seller_id = True
        except Exception:
            await db.rollback()
            # Колонка не добавлена, используем raw SQL
    
    # Если колонка существует, используем ORM
    if has_seller_id:
        try:
            query = select(ShopListing)
            
            if active_only:
                query = query.where(ShopListing.is_active == True)
            
            # Не показываем товары с stock = 0 (если stock не None)
            query = query.where(
                or_(
                    ShopListing.stock.is_(None),  # Неограниченный товар
                    ShopListing.stock > 0  # Есть в наличии
                )
            )
            
            query = query.offset(skip).limit(limit)
            result = await db.execute(query)
            listings = result.scalars().all()
            return listings
        except Exception:
            # Если всё ещё ошибка, используем raw SQL
            has_seller_id = False
    
    # Используем raw SQL, если колонки нет или произошла ошибка
    if not has_seller_id:
        active_condition = "AND is_active = true" if active_only else ""
        sql = text(f"""
            SELECT id, item_id, price, stock, is_active, created_at, updated_at
            FROM shop_listings
            WHERE (stock IS NULL OR stock > 0)
            {active_condition}
            LIMIT :limit OFFSET :skip
        """)
        result = await db.execute(sql, {"limit": limit, "skip": skip})
        rows = result.fetchall()
        # Преобразуем в Pydantic модели
        listings = []
        for row in rows:
            listings.append(ShopListingResponse(
                id=row[0],
                seller_id=None,
                item_id=row[1],
                price=row[2],
                stock=row[3],
                is_active=row[4]
            ))
        return listings

@app.get("/shop/listings/{listing_id}", response_model=ShopListingResponse)
async def get_shop_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Получить товар по ID"""
    result = await db.execute(select(ShopListing).where(ShopListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Товар не найден")
    return listing

@app.put("/shop/listings/{listing_id}", response_model=ShopListingResponse)
async def update_shop_listing(
    listing_id: int,
    listing_in: ShopListingUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Обновить товар"""
    result = await db.execute(select(ShopListing).where(ShopListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    # Сохраняем старое значение is_active для проверки изменения
    old_is_active = listing.is_active
    
    update_data = listing_in.model_dump(exclude_unset=True)
    
    # Обработка изменения статуса is_active
    if "is_active" in update_data:
        new_is_active = update_data["is_active"]
        
        # Если товар снимается с продажи (True -> False)
        if old_is_active and not new_is_active:
            # Возвращаем предмет в инвентарь продавца (только оставшееся количество)
            if listing.seller_id is not None:
                quantity_to_return = listing.stock if listing.stock is not None else 1
                if quantity_to_return > 0:
                    inventory_service = ServiceClient("inventory")
                    try:
                        await inventory_service.post(
                            f"/items/add-to-user/{listing.seller_id}",
                            params={"item_id": listing.item_id, "quantity": quantity_to_return}
                        )
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"Ошибка при возврате предмета в инвентарь: {str(e)}")
                    finally:
                        await inventory_service.close()
        
        # Если товар снова выставляется на продажу (False -> True)
        elif not old_is_active and new_is_active:
            # Удаляем предмет из инвентаря продавца
            if listing.seller_id is not None:
                quantity_to_remove = listing.stock if listing.stock is not None else 1
                if quantity_to_remove > 0:
                    inventory_service = ServiceClient("inventory")
                    try:
                        # Проверяем наличие предмета у продавца
                        inventory = await inventory_service.get(f"/inventory/users/{listing.seller_id}")
                        user_item = next((item for item in inventory if item.get("item_id") == listing.item_id), None)
                        
                        if not user_item:
                            raise HTTPException(status_code=400, detail="У вас нет этого предмета в инвентаре")
                        
                        if user_item.get("quantity", 0) < quantity_to_remove:
                            raise HTTPException(status_code=400, detail=f"Недостаточно предметов. У вас: {user_item.get('quantity', 0)}, требуется: {quantity_to_remove}")
                        
                        # Удаляем предмет из инвентаря
                        await inventory_service.post(
                            f"/inventory/users/{listing.seller_id}/items/remove",
                            params={"item_id": listing.item_id, "quantity": quantity_to_remove}
                        )
                    except HTTPException:
                        raise
                    except Exception as e:
                        raise HTTPException(status_code=500, detail=f"Ошибка при удалении предмета из инвентаря: {str(e)}")
                    finally:
                        await inventory_service.close()
    
    # Применяем остальные изменения
    for field, value in update_data.items():
        if field != "is_active":  # is_active уже обработан выше
            setattr(listing, field, value)
    
    await db.commit()
    await db.refresh(listing)
    return listing

@app.delete("/shop/listings/{listing_id}", response_model=ShopListingResponse)
async def delete_shop_listing(listing_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить товар из магазина (предмет возвращается в инвентарь продавца)"""
    result = await db.execute(select(ShopListing).where(ShopListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    # Возвращаем предмет в инвентарь продавца только если есть seller_id
    # и товар был активен (иначе предмет уже в инвентаре)
    if listing.seller_id is not None and listing.is_active:
        # Возвращаем только оставшееся количество из stock
        quantity_to_return = listing.stock if listing.stock is not None else 1
        if quantity_to_return > 0:
            inventory_service = ServiceClient("inventory")
            try:
                await inventory_service.post(
                    f"/items/add-to-user/{listing.seller_id}",
                    params={"item_id": listing.item_id, "quantity": quantity_to_return}
                )
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Ошибка при возврате предмета в инвентарь: {str(e)}")
            finally:
                await inventory_service.close()
    
    # Удаляем листинг
    await db.delete(listing)
    await db.commit()
    return listing

# Покупки
@app.post("/shop/listings/{listing_id}/purchase")
async def purchase_item(
    listing_id: int,
    purchase_in: PurchaseRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Купить предмет из магазина
    1. Проверить наличие монет у пользователя
    2. Списать монеты через Character Service
    3. Добавить предмет через Inventory Service
    4. Создать транзакцию
    """
    # Получить товар
    result = await db.execute(select(ShopListing).where(ShopListing.id == listing_id))
    listing = result.scalar_one_or_none()
    if not listing:
        raise HTTPException(status_code=404, detail="Товар не найден")
    
    if not listing.is_active:
        raise HTTPException(status_code=400, detail="Товар недоступен для покупки")
    
    # Проверить наличие на складе
    if listing.stock is not None:
        if listing.stock <= 0:
            raise HTTPException(status_code=400, detail="Товар закончился")
        if listing.stock < purchase_in.quantity:
            raise HTTPException(status_code=400, detail="Недостаточно товара на складе")
    
    total_price = listing.price * purchase_in.quantity
    
    # Получить пользователя и проверить монеты
    result = await db.execute(select(User).where(User.id == purchase_in.user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    # Проверить достаточность монет
    if user.coins < total_price:
        raise HTTPException(status_code=400, detail=f"Недостаточно монет. Требуется: {total_price}, доступно: {user.coins}")
    
    # Получить персонажа пользователя
    result = await db.execute(
        select(Character).where(Character.user_id == purchase_in.user_id)
    )
    character = result.scalar_one_or_none()
    if not character:
        raise HTTPException(status_code=404, detail="Персонаж пользователя не найден")
    
    # Получить продавца (если есть seller_id)
    seller = None
    if listing.seller_id is not None:
        result = await db.execute(select(User).where(User.id == listing.seller_id))
        seller = result.scalar_one_or_none()
        if not seller:
            raise HTTPException(status_code=404, detail="Продавец не найден")
    
    # Списать монеты у покупателя через User Service
    user_service = ServiceClient("user")
    try:
        await user_service.post(f"/users/{user.id}/coins/subtract", json={
            "amount": total_price
        })
        
        # Перевести деньги продавцу (только если есть seller_id)
        if listing.seller_id is not None:
            try:
                await user_service.post(f"/users/{listing.seller_id}/coins/add", json={
                    "amount": total_price
                })
            except Exception as e:
                # Откатить списание монет у покупателя
                await user_service.post(f"/users/{user.id}/coins/add", json={
                    "amount": total_price
                })
                raise HTTPException(status_code=500, detail=f"Ошибка при переводе денег продавцу: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при списании монет: {str(e)}")
    finally:
        await user_service.close()
    
    # Добавить предмет в инвентарь покупателя через Inventory Service
    inventory_service = ServiceClient("inventory")
    try:
        await inventory_service.post(
            f"/items/add-to-user/{purchase_in.user_id}",
            params={"item_id": listing.item_id, "quantity": purchase_in.quantity}
        )
    except Exception as e:
        # Откатить транзакции
        user_service = ServiceClient("user")
        await user_service.post(f"/users/{user.id}/coins/add", json={"amount": total_price})
        if listing.seller_id is not None:
            await user_service.post(f"/users/{listing.seller_id}/coins/subtract", json={"amount": total_price})
        await user_service.close()
        raise HTTPException(status_code=500, detail=f"Ошибка при добавлении предмета: {str(e)}")
    finally:
        await inventory_service.close()
    
    # Уменьшить количество на складе
    if listing.stock is not None:
        listing.stock -= purchase_in.quantity
        await db.commit()
    
    # Создать транзакцию для покупателя
    buyer_transaction = Transaction(
        user_id=purchase_in.user_id,
        type=TransactionType.PURCHASE,
        amount=-total_price,
        description=f"Покупка предмета (listing_id={listing_id})",
        related_item_id=listing.item_id,
        related_user_id=listing.seller_id
    )
    db.add(buyer_transaction)
    
    # Создать транзакцию для продавца (если есть seller_id)
    seller_transaction = None
    if listing.seller_id is not None:
        seller_transaction = Transaction(
            user_id=listing.seller_id,
            type=TransactionType.SALE,
            amount=total_price,
            description=f"Продажа предмета (listing_id={listing_id})",
            related_item_id=listing.item_id,
            related_user_id=purchase_in.user_id
        )
        db.add(seller_transaction)
    
    await db.commit()
    await db.refresh(buyer_transaction)
    if seller_transaction:
        await db.refresh(seller_transaction)
    
    # Отправляем уведомление продавцу о покупке товара (если есть seller_id)
    if listing.seller_id is not None:
        try:
            bot_service = ServiceClient("max_bot")
            result = await db.execute(select(User).where(User.id == purchase_in.user_id))
            buyer = result.scalar_one_or_none()
            buyer_username = buyer.username if buyer else None
            
            result = await db.execute(select(Item).where(Item.id == listing.item_id))
            item = result.scalar_one_or_none()
            item_name = item.name if item else "предмет"
            
            await bot_service.post("/notifications/shop-purchase", json={
                "seller_user_id": listing.seller_id,
                "buyer_username": buyer_username,
                "item_name": item_name,
                "quantity": purchase_in.quantity,
                "total_price": total_price
            })
            await bot_service.close()
        except Exception as e:
            logger.warning(f"Не удалось отправить уведомление о покупке товара: {e}")
    
    return {
        "success": True,
        "listing_id": listing_id,
        "item_id": listing.item_id,
        "quantity": purchase_in.quantity,
        "total_price": total_price,
        "buyer_transaction": TransactionResponse.model_validate(buyer_transaction),
        "seller_transaction": TransactionResponse.model_validate(seller_transaction) if seller_transaction else None
    }

# Транзакции
@app.get("/transactions/", response_model=List[TransactionResponse])
async def list_transactions(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db)
):
    """Список всех транзакций"""
    result = await db.execute(
        select(Transaction).order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()

@app.get("/transactions/{transaction_id}", response_model=TransactionResponse)
async def get_transaction(transaction_id: int, db: AsyncSession = Depends(get_db)):
    """Получить транзакцию по ID"""
    result = await db.execute(select(Transaction).where(Transaction.id == transaction_id))
    transaction = result.scalar_one_or_none()
    if not transaction:
        raise HTTPException(status_code=404, detail="Транзакция не найдена")
    return transaction

@app.get("/transactions/users/{user_id}", response_model=List[TransactionResponse])
async def get_user_transactions(
    user_id: int,
    skip: int = 0,
    limit: int = 100,
    transaction_type: Optional[TransactionType] = None,
    db: AsyncSession = Depends(get_db)
):
    """Получить транзакции пользователя"""
    query = select(Transaction).where(Transaction.user_id == user_id)
    
    if transaction_type:
        query = query.where(Transaction.type == transaction_type)
    
    query = query.order_by(Transaction.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

class TransferCoinsRequest(BaseModel):
    from_user_id: int
    to_user_id: int
    amount: int = Field(..., gt=0)

@app.post("/transactions/transfer")
async def transfer_coins(
    request: TransferCoinsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Перевести монеты от одного пользователя другому"""
    if request.from_user_id == request.to_user_id:
        raise HTTPException(status_code=400, detail="Нельзя перевести монеты самому себе")
    
    # Получить пользователей
    result = await db.execute(select(User).where(User.id == request.from_user_id))
    from_user = result.scalar_one_or_none()
    if not from_user:
        raise HTTPException(status_code=404, detail="Пользователь-отправитель не найден")
    
    result = await db.execute(select(User).where(User.id == request.to_user_id))
    to_user = result.scalar_one_or_none()
    if not to_user:
        raise HTTPException(status_code=404, detail="Пользователь-получатель не найден")
    
    # Проверить достаточность монет
    if from_user.coins < request.amount:
        raise HTTPException(status_code=400, detail="Недостаточно монет")
    
    # Выполнить перевод через User Service
    user_service = ServiceClient("user")
    try:
        # Списать у отправителя
        await user_service.post(f"/users/{from_user.id}/coins/subtract", json={
            "amount": request.amount
        })
        
        # Начислить получателю
        await user_service.post(f"/users/{to_user.id}/coins/add", json={
            "amount": request.amount
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при переводе: {str(e)}")
    finally:
        await user_service.close()
    
    # Создать транзакции
    transaction_from = Transaction(
        user_id=request.from_user_id,
        type=TransactionType.TRANSFER,
        amount=-request.amount,
        description=f"Перевод пользователю {request.to_user_id}",
        related_user_id=request.to_user_id
    )
    transaction_to = Transaction(
        user_id=request.to_user_id,
        type=TransactionType.TRANSFER,
        amount=request.amount,
        description=f"Получен перевод от пользователя {request.from_user_id}",
        related_user_id=request.from_user_id
    )
    db.add(transaction_from)
    db.add(transaction_to)
    await db.commit()
    
    return {
        "success": True,
        "from_user_id": request.from_user_id,
        "to_user_id": request.to_user_id,
        "amount": request.amount
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8009)

