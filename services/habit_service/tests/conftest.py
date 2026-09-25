"""
Фикстуры для тестов Habit Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from services.habit_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.test_utils import generate_user_data, generate_habit_data, MockServiceClient


@pytest_asyncio.fixture
async def client(test_db_session: AsyncSession):
    """Создать тестовый HTTP клиент"""
    async def override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_user(test_db_session: AsyncSession):
    """Создать тестового пользователя"""
    user_data = generate_user_data()
    user = User(**user_data)
    test_db_session.add(user)
    await test_db_session.commit()
    await test_db_session.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email}


@pytest_asyncio.fixture
async def sample_habit(client, sample_user):
    """Создать тестовую привычку"""
    habit_data = generate_habit_data(sample_user["id"])
    response = await client.post(f"/habits/?user_id={sample_user['id']}", json=habit_data)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def mock_reward_service():
    """Мокировать Reward Service"""
    mock = MockServiceClient("reward")
    mock.set_response("/rewards/grant", {
        "user_id": 1,
        "coins_added": 5,
        "intelligence_added": 2,
        "satisfaction_added": 0,
        "level_up": False,
        "achievements_earned": []
    })
    
    with patch("services.habit_service.main.ServiceClient", return_value=mock):
        yield mock

