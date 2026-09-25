"""
Фикстуры для тестов User Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from services.user_service.main import app
from services.shared.database import get_db
from services.test_utils import generate_user_data


@pytest_asyncio.fixture
async def client(test_db_session: AsyncSession):
    """Создать тестовый HTTP клиент"""
    async def override_get_db():
        yield test_db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    from httpx import ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def sample_user(client):
    """Создать тестового пользователя"""
    user_data = generate_user_data()
    response = await client.post("/users/", json=user_data)
    assert response.status_code == 201
    return response.json()

