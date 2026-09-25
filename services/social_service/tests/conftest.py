"""
Фикстуры для тестов Social Service
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from services.social_service.main import app
from services.shared.database import get_db
from services.shared.models.user import User
from services.test_utils import generate_user_data, generate_clan_data


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
async def sample_clan(client, sample_user):
    clan_data = generate_clan_data()
    response = await client.post(
        "/clans/",
        params={"creator_user_id": sample_user['id']},
        json=clan_data
    )
    return response.json()


@pytest_asyncio.fixture
async def test_db_session(test_db_session: AsyncSession):
    """Экспорт test_db_session для использования в тестах"""
    yield test_db_session
