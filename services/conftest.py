"""
Общие фикстуры pytest для всех микросервисов
"""
import os

# Окружение тестов: авторизация в мягком режиме, токен администратора не задан
os.environ.setdefault("AUTH_MODE", "lenient")
os.environ["ADMIN_TOKEN"] = ""  # пустое значение: load_dotenv не подставит токен из локального .env
os.environ.setdefault("MAX_BOT_TOKEN", "test-bot-token")
os.environ.setdefault("CHECKIN_ENFORCE_WINDOW", "false")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@postgres:5432/tamagotchi_db")

import pytest
import pytest_asyncio
import asyncio
from typing import AsyncGenerator, Generator
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

from services.shared.database import Base
import services.shared.models  # noqa: F401 — регистрирует все таблицы в metadata


# Настройка event loop для pytest-asyncio
@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Создать event loop для всей сессии тестирования"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def test_db_engine():
    """
    Создать тестовый движок БД (SQLite в памяти) для каждого теста
    """
    # SQLite в памяти для быстрых тестов
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    
    # Создать все таблицы
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Очистить после теста
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def test_db_session(test_db_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Создать тестовую сессию БД для каждого теста
    """
    async_session_maker = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()

