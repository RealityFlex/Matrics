"""
Фикстуры для тестов Economy Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from services.economy_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.shared.models.item import Item
from services.shared.models.character import Character
from services.test_utils import generate_user_data, generate_item_data, MockServiceClient


@pytest_asyncio.fixture
async def client(test_db_session: AsyncSession):
    async def override_get_db():
        yield test_db_session
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_user(test_db_session: AsyncSession):
    user_data = generate_user_data()
    user = User(**user_data)
    # Установить монеты пользователю
    user.coins = 1000
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    
    # Создать персонажа
    character = Character(user_id=user.id, name="Test")
    test_db_session.add(character)
    await test_db_session.commit()
    
    return {"id": user.id, "character_id": character.id}


@pytest_asyncio.fixture
async def sample_item(test_db_session: AsyncSession):
    item_data = generate_item_data()
    # Convert enum string values to enum instances
    from services.shared.models.item import ItemRarity, ItemType
    rarity = next((m for m in ItemRarity if m.value == item_data["rarity"]), ItemRarity.COMMON)
    item_type = next((m for m in ItemType if m.value == item_data["type"]), ItemType.CONSUMABLE)
    
    item = Item(
        name=item_data["name"],
        description=item_data["description"],
        rarity=rarity,
        type=item_type,
        base_price=item_data["base_price"]
    )
    test_db_session.add(item)
    await test_db_session.commit()
    await test_db_session.refresh(item)
    return {"id": item.id}


@pytest_asyncio.fixture
async def test_db_session(test_db_session: AsyncSession):
    """Экспорт test_db_session для использования в тестах"""
    yield test_db_session


@pytest.fixture
def mock_services():
    user_mock = MockServiceClient("user")
    user_mock.set_response("/coins/subtract", {"success": True})
    user_mock.set_response("/coins/add", {"success": True})
    
    inventory_mock = MockServiceClient("inventory")
    inventory_mock.set_response("/items/add", {"success": True, "quantity": 1})
    
    with patch("services.economy_service.main.ServiceClient") as mock:
        def side_effect(service_name):
            if service_name == "user":
                return user_mock
            return inventory_mock
        mock.side_effect = side_effect
        yield mock

