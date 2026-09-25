"""
Фикстуры для тестов Character Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from services.character_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.test_utils import generate_user_data, generate_character_data


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
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "coins": user.coins
    }


@pytest_asyncio.fixture
async def sample_character(client, sample_user):
    """Создать тестового персонажа"""
    char_data = generate_character_data(sample_user["id"])
    response = await client.post("/characters/", json=char_data)
    assert response.status_code == 201
    return response.json()

