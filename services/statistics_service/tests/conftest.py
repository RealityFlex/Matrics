"""
Фикстуры для тестов Statistics Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession
from unittest.mock import patch

from services.statistics_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
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
    return {"id": user.id, "username": user.username, "email": user.email}


@pytest.fixture
def mock_services():
    # Мокировать все сервисы
    service_mock = MockServiceClient("service")
    service_mock.set_response("/characters", {"satisfaction": 50, "rating": 115})
    service_mock.set_response("/tasks/stats", {"total": 10, "completed": 5})
    service_mock.set_response("/habits/stats", {"total_habits": 3})
    service_mock.set_response("/inventory", [])
    service_mock.set_response("/achievements/stats", {"completed": 2})
    service_mock.set_response("/events/stats", {"attended_events": 5})
    service_mock.set_response("/competitions/stats", {"total_competitions": 3})
    
    with patch("services.statistics_service.main.ServiceClient", return_value=service_mock):
        yield service_mock

