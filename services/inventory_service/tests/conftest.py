"""
Фикстуры для тестов Inventory Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from services.inventory_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.shared.models.item import Item, ItemRarity, ItemType
from services.test_utils import generate_user_data, generate_item_data


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
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return {"id": user.id}


@pytest_asyncio.fixture
async def sample_item(test_db_session: AsyncSession):
    item_data = generate_item_data()
    # Convert enum string values to enum instances (find by value)
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
    return {"id": item.id, "name": item.name}

