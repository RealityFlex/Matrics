"""
Фикстуры для тестов Reward Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch, AsyncMock

from services.reward_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.shared.models.character import Character
from services.test_utils import generate_user_data, MockServiceClient


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
    
    # Создать персонажа
    character = Character(user_id=user.id, name="Test")
    test_db_session.add(character)
    await test_db_session.commit()
    await test_db_session.refresh(character)
    
    return {"id": user.id, "character_id": character.id}


@pytest.fixture
def mock_services():
    user_mock = MockServiceClient("user")
    user_mock.set_response("/users", {"id": 1, "coins": 100})
    
    character_mock = MockServiceClient("character")
    character_mock.set_response("/characters/user", {"id": 1, "intelligence_level": 1})
    character_mock.set_response("/characters/1/intelligence/add", {
        "character_id": 1,
        "intelligence_level": 1,
        "intelligence_points": 10,
        "level_up": False,
        "levels_gained": 0
    })
    character_mock.set_response("/characters/1/satisfaction/adjust", {"success": True})
    
    inventory_mock = MockServiceClient("inventory")
    inventory_mock.set_response("/inventory", {"success": True})
    
    achievement_mock = MockServiceClient("achievement")
    achievement_mock.set_response("/achievements/check", {"earned": []})
    
    with patch("services.reward_service.main.ServiceClient") as mock:
        def side_effect(service_name):
            if service_name == "user":
                return user_mock
            elif service_name == "character":
                return character_mock
            elif service_name == "inventory":
                return inventory_mock
            return achievement_mock
        mock.side_effect = side_effect
        yield mock

