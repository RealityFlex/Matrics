"""
Фикстуры для тестов Competition Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from services.competition_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.test_utils import generate_user_data, generate_competition_data, MockServiceClient


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
async def sample_competition(client):
    competition_data = generate_competition_data()
    response = await client.post("/competitions/", json=competition_data)
    return response.json()


@pytest_asyncio.fixture
async def test_db_session(test_db_session: AsyncSession):
    """Экспорт test_db_session для использования в тестах"""
    yield test_db_session


@pytest.fixture
def mock_reward_service():
    mock = MockServiceClient("reward")
    mock.set_response("/rewards/grant", {
        "user_id": 1,
        "coins_added": 1000,
        "intelligence_added": 0,
        "satisfaction_added": 0,
        "level_up": False,
        "achievements_earned": []
    })
    with patch("services.competition_service.main.ServiceClient", return_value=mock):
        yield mock

