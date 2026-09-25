"""
Unit тесты для Inventory Service
"""
import pytest
from httpx import AsyncClient

from services.test_utils import generate_item_data, generate_user_data
from services.shared.models.user import User


class TestItemCRUD:
    """Тесты CRUD для предметов"""
    
    @pytest.mark.asyncio
    async def test_create_item(self, client: AsyncClient):
        item_data = generate_item_data()
        response = await client.post("/items/", json=item_data)
        assert response.status_code == 201
        assert response.json()["name"] == item_data["name"]
    
    @pytest.mark.asyncio
    async def test_list_items(self, client: AsyncClient, sample_item):
        response = await client.get("/items/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_get_item_by_id(self, client: AsyncClient, sample_item):
        response = await client.get(f"/items/{sample_item['id']}")
        assert response.status_code == 200


class TestInventory:
    """Тесты инвентаря пользователей"""
    
    @pytest.mark.asyncio
    async def test_get_user_inventory_empty(self, client: AsyncClient, sample_user):
        response = await client.get(f"/inventory/users/{sample_user['id']}")
        assert response.status_code == 200
        assert response.json() == []
    
    @pytest.mark.asyncio
    async def test_add_item_to_inventory(self, client: AsyncClient, sample_user, sample_item):
        response = await client.post(
            f"/inventory/users/{sample_user['id']}/items/add?item_id={sample_item['id']}&quantity=5"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["quantity"] == 5
    
    @pytest.mark.asyncio
    async def test_remove_item_from_inventory(self, client: AsyncClient, sample_user, sample_item):
        # Добавить
        await client.post(
            f"/inventory/users/{sample_user['id']}/items/add?item_id={sample_item['id']}&quantity=10"
        )
        # Удалить
        response = await client.post(
            f"/inventory/users/{sample_user['id']}/items/remove?item_id={sample_item['id']}&quantity=3"
        )
        assert response.status_code == 200
        assert response.json()["remaining"] == 7
    
    @pytest.mark.asyncio
    async def test_transfer_item_between_users(
        self, client: AsyncClient, sample_user, sample_item, test_db_session
    ):
        # Создать второго пользователя
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Добавить предмет первому пользователю
        await client.post(
            f"/inventory/users/{sample_user['id']}/items/add?item_id={sample_item['id']}&quantity=10"
        )
        
        # Передать второму
        response = await client.post(
            f"/inventory/users/{sample_user['id']}/items/transfer",
            params={"target_user_id": user2.id, "item_id": sample_item['id'], "quantity": 3}
        )
        assert response.status_code == 200
        assert response.json()["success"] is True

