"""
Unit тесты для Economy Service - Покупка и обмен предметов
"""
import pytest
from httpx import AsyncClient
from services.test_utils import generate_user_data
from services.shared.models.user import User
from services.shared.models.item import Item, ItemRarity, ItemType
from services.shared.models.character import Character
from sqlalchemy import select


class TestShopListings:
    """Тесты для товаров в магазине"""
    
    @pytest.mark.asyncio
    async def test_create_shop_listing(self, client: AsyncClient, sample_item):
        """Создание товара в магазине"""
        listing_data = {"item_id": sample_item['id'], "price": 100, "stock": 50}
        response = await client.post("/shop/listings/", json=listing_data)
        assert response.status_code == 201
        data = response.json()
        assert data["item_id"] == sample_item["id"]
        assert data["price"] == 100
        assert data["stock"] == 50
        assert data["is_active"] is True
    
    @pytest.mark.asyncio
    async def test_create_shop_listing_item_not_found(self, client: AsyncClient):
        """Ошибка при создании товара для несуществующего предмета"""
        listing_data = {"item_id": 99999, "price": 100}
        response = await client.post("/shop/listings/", json=listing_data)
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_create_shop_listing_negative_price(self, client: AsyncClient, sample_item):
        """Ошибка при создании товара с отрицательной ценой"""
        listing_data = {"item_id": sample_item['id'], "price": -100}
        response = await client.post("/shop/listings/", json=listing_data)
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_list_shop_listings(self, client: AsyncClient, sample_item):
        """Получение списка товаров в магазине"""
        # Создать листинг
        listing_data = {"item_id": sample_item['id'], "price": 100}
        await client.post("/shop/listings/", json=listing_data)
        
        response = await client.get("/shop/listings/")
        assert response.status_code == 200
        listings = response.json()
        assert isinstance(listings, list)
        assert len(listings) >= 1
    
    @pytest.mark.asyncio
    async def test_list_shop_listings_active_only(self, client: AsyncClient, sample_item):
        """Получение только активных товаров"""
        # Создать активный и неактивный листинг
        active_listing = {"item_id": sample_item['id'], "price": 100, "is_active": True}
        await client.post("/shop/listings/", json=active_listing)
        
        response = await client.get("/shop/listings/?active_only=true")
        assert response.status_code == 200
        listings = response.json()
        assert all(listing["is_active"] for listing in listings)
    
    @pytest.mark.asyncio
    async def test_get_shop_listing_by_id(self, client: AsyncClient, sample_item):
        """Получение товара по ID"""
        listing_data = {"item_id": sample_item['id'], "price": 100}
        create_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = create_response.json()["id"]
        
        response = await client.get(f"/shop/listings/{listing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == listing_id
    
    @pytest.mark.asyncio
    async def test_update_shop_listing(self, client: AsyncClient, sample_item):
        """Обновление товара в магазине"""
        listing_data = {"item_id": sample_item['id'], "price": 100}
        create_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = create_response.json()["id"]
        
        update_data = {"price": 150, "stock": 100}
        response = await client.put(f"/shop/listings/{listing_id}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["price"] == 150
        assert data["stock"] == 100
    
    @pytest.mark.asyncio
    async def test_delete_shop_listing(self, client: AsyncClient, sample_item):
        """Удаление товара из магазина"""
        listing_data = {"item_id": sample_item['id'], "price": 100}
        create_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = create_response.json()["id"]
        
        response = await client.delete(f"/shop/listings/{listing_id}")
        assert response.status_code == 200


class TestItemPurchase:
    """Тесты для покупки предметов"""
    
    @pytest.mark.asyncio
    async def test_purchase_item_success(self, client: AsyncClient, sample_user, sample_item, mock_services):
        """Успешная покупка предмета"""
        # Создать товар в магазине
        listing_data = {"item_id": sample_item['id'], "price": 100, "stock": 10}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        # Моки уже настроены в фикстуре
        
        # Купить предмет
        purchase_data = {"user_id": sample_user['id'], "quantity": 1}
        response = await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["quantity"] == 1
        assert data["total_price"] == 100
        assert "transaction" in data
    
    @pytest.mark.asyncio
    async def test_purchase_item_insufficient_coins(self, client: AsyncClient, sample_user, sample_item, test_db_session):
        """Ошибка при покупке из-за недостатка монет"""
        # Установить недостаточное количество монет пользователю
        from services.shared.models.user import User
        result = await test_db_session.execute(
            select(User).where(User.id == sample_user['id'])
        )
        user = result.scalar_one_or_none()
        user.coins = 50  # Недостаточно для покупки
        await test_db_session.commit()
        
        # Создать товар в магазине
        listing_data = {"item_id": sample_item['id'], "price": 100}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        # Попытка купить (должна вернуть ошибку)
        purchase_data = {"user_id": sample_user['id'], "quantity": 1}
        response = await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        assert response.status_code == 400
        assert "Недостаточно монет" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_purchase_item_insufficient_stock(self, client: AsyncClient, sample_user, sample_item, mock_services):
        """Ошибка при покупке из-за недостатка товара на складе"""
        # Создать товар с ограниченным количеством
        listing_data = {"item_id": sample_item['id'], "price": 100, "stock": 5}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        # Попытка купить больше, чем есть
        purchase_data = {"user_id": sample_user['id'], "quantity": 10}
        response = await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        assert response.status_code == 400
        assert "Недостаточно товара" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_purchase_item_inactive_listing(self, client: AsyncClient, sample_user, sample_item):
        """Ошибка при покупке неактивного товара"""
        # Создать неактивный товар
        listing_data = {"item_id": sample_item['id'], "price": 100, "is_active": False}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        purchase_data = {"user_id": sample_user['id'], "quantity": 1}
        response = await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        assert response.status_code == 400
        assert "недоступен" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_purchase_item_multiple_quantity(self, client: AsyncClient, sample_user, sample_item, mock_services):
        """Покупка нескольких предметов"""
        listing_data = {"item_id": sample_item['id'], "price": 50, "stock": 20}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        # Моки уже настроены в фикстуре
        
        purchase_data = {"user_id": sample_user['id'], "quantity": 5}
        response = await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 5
        assert data["total_price"] == 250  # 50 * 5
    
    @pytest.mark.asyncio
    async def test_purchase_item_stock_decreases(self, client: AsyncClient, sample_user, sample_item, mock_services):
        """Уменьшение количества товара на складе после покупки"""
        initial_stock = 10
        listing_data = {"item_id": sample_item['id'], "price": 100, "stock": initial_stock}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        # Моки уже настроены в фикстуре
        
        purchase_data = {"user_id": sample_user['id'], "quantity": 3}
        await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        
        # Проверить, что количество уменьшилось
        response = await client.get(f"/shop/listings/{listing_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["stock"] == initial_stock - 3


class TestTransactions:
    """Тесты для транзакций"""
    
    @pytest.mark.asyncio
    async def test_list_transactions(self, client: AsyncClient):
        """Получение списка транзакций"""
        response = await client.get("/transactions/")
        assert response.status_code == 200
        transactions = response.json()
        assert isinstance(transactions, list)
    
    @pytest.mark.asyncio
    async def test_get_user_transactions(self, client: AsyncClient, sample_user):
        """Получение транзакций пользователя"""
        response = await client.get(f"/transactions/users/{sample_user['id']}")
        assert response.status_code == 200
        transactions = response.json()
        assert isinstance(transactions, list)
    
    @pytest.mark.asyncio
    async def test_transaction_created_after_purchase(self, client: AsyncClient, sample_user, sample_item, mock_services):
        """Создание транзакции после покупки"""
        listing_data = {"item_id": sample_item['id'], "price": 100}
        listing_response = await client.post("/shop/listings/", json=listing_data)
        listing_id = listing_response.json()["id"]
        
        # Моки уже настроены в фикстуре
        
        purchase_data = {"user_id": sample_user['id'], "quantity": 1}
        purchase_response = await client.post(
            f"/shop/listings/{listing_id}/purchase",
            json=purchase_data
        )
        
        # Проверить транзакции пользователя
        response = await client.get(f"/transactions/users/{sample_user['id']}")
        assert response.status_code == 200
        transactions = response.json()
        assert len(transactions) >= 1
        # Найти транзакцию покупки
        purchase_transactions = [t for t in transactions if t["type"] == "purchase"]
        assert len(purchase_transactions) >= 1
