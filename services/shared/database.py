"""
Конфигурация базы данных и сессий SQLAlchemy для всех микросервисов
"""
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import ProgrammingError, IntegrityError
import os
from dotenv import load_dotenv
import logging
import asyncio

logger = logging.getLogger(__name__)

load_dotenv()

# URL подключения к базе данных из переменных окружения
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@postgres:5432/tamagotchi_db")

# Создание асинхронного движка
engine = create_async_engine(
    DATABASE_URL,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Логирование SQL запросов (только для отладки)
    future=True,
    pool_pre_ping=True,
)

# Фабрика асинхронных сессий
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

# Базовый класс для моделей
Base = declarative_base()


# Зависимость для получения сессии БД в эндпоинтах
async def get_db():
    """
    Dependency для получения асинхронной сессии базы данных
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Функция для создания всех таблиц
async def init_db(max_retries: int = 5, retry_delay: float = 1.0):
    """
    Инициализация базы данных - создание всех таблиц
    Использует checkfirst=True для проверки существования объектов перед созданием
    Обрабатывает ошибки дублирования для enum типов и таблиц
    Выполняет повторные попытки при ошибках параллельного доступа
    """
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all, checkfirst=True)
            logger.info("База данных успешно инициализирована")
            return
        except (ProgrammingError, IntegrityError) as e:
            # Игнорируем ошибки дублирования enum типов и таблиц
            # Это может произойти при одновременном запуске нескольких сервисов
            error_str = str(e.orig) if hasattr(e, 'orig') else str(e)
            error_msg = str(e)
            
            # Проверяем различные варианты сообщений об ошибках
            if any(keyword in error_str.lower() or keyword in error_msg.lower() 
                   for keyword in ["already exists", "duplicate key", "duplicate table", "duplicate type", 
                                   "pg_type_typname_nsp_index", "cached plan"]):
                logger.warning(f"Объект БД уже существует (это нормально при параллельном запуске): {error_str}")
                # Продолжаем работу, так как объекты уже существуют
                return
            else:
                # Если это другая ошибка и не последняя попытка, повторяем
                if attempt < max_retries - 1:
                    logger.warning(f"Ошибка при создании объектов БД (попытка {attempt + 1}/{max_retries}): {error_str}. Повтор через {retry_delay}с...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Ошибка при создании объектов БД после {max_retries} попыток: {error_str}")
                    raise
        except Exception as e:
            # Обрабатываем другие типы исключений (например, обернутые asyncpg исключения)
            error_str = str(e)
            if any(keyword in error_str.lower() 
                   for keyword in ["already exists", "duplicate key", "duplicate table", "duplicate type",
                                   "pg_type_typname_nsp_index", "cached plan"]):
                logger.warning(f"Объект БД уже существует (это нормально при параллельном запуске): {error_str}")
                return
            else:
                # Если это другая ошибка и не последняя попытка, повторяем
                if attempt < max_retries - 1:
                    logger.warning(f"Неожиданная ошибка при создании объектов БД (попытка {attempt + 1}/{max_retries}): {error_str}. Повтор через {retry_delay}с...")
                    await asyncio.sleep(retry_delay)
                    continue
                else:
                    logger.error(f"Неожиданная ошибка при создании объектов БД после {max_retries} попыток: {error_str}")
                    raise


async def execute_migration_sql(migration_sql: str, max_retries: int = 3, retry_delay: float = 0.5, initial_delay: float = 0.5):
    """
    Выполнить SQL миграцию, разделяя многострочные SQL на отдельные команды.
    Каждая команда выполняется отдельно, чтобы избежать ошибок "cannot insert multiple commands into a prepared statement"
    
    Args:
        migration_sql: SQL код миграции (может содержать несколько команд)
        max_retries: Максимальное количество попыток
        retry_delay: Задержка между попытками (в секундах)
        initial_delay: Задержка перед началом миграции (для избежания конфликтов при параллельном запуске)
    """
    # Небольшая задержка перед началом миграции для избежания конфликтов
    if initial_delay > 0:
        await asyncio.sleep(initial_delay)
    # Разделяем SQL на отдельные команды
    # Обрабатываем DO $$ блоки как единое целое
    commands = []
    current_command = []
    in_do_block = False
    
    for line in migration_sql.split('\n'):
        stripped = line.strip()
        
        # Пропускаем пустые строки и комментарии (если не внутри DO блока)
        if not in_do_block and (not stripped or stripped.startswith('--')):
            continue
        
        # Отслеживаем начало DO $$ блока
        if 'DO $$' in stripped.upper() or (not in_do_block and 'DO' in stripped.upper() and '$$' in stripped):
            in_do_block = True
        
        # Добавляем строку к текущей команде
        current_command.append(line)
        
        # Отслеживаем конец DO $$ блока (ищем "END $$;" или "END$$;")
        if in_do_block:
            # Проверяем, содержит ли строка конец DO блока
            if 'END' in stripped.upper() and '$$' in stripped and ';' in stripped:
                in_do_block = False
                # Команда завершена
                command = '\n'.join(current_command).strip()
                if command:
                    commands.append(command)
                current_command = []
                continue
        
        # Если команда завершена (точка с запятой и не внутри DO блока)
        if not in_do_block and stripped.endswith(';'):
            command = '\n'.join(current_command).strip()
            if command:
                commands.append(command)
            current_command = []
    
    # Если осталась незавершенная команда, добавляем её
    if current_command:
        command = '\n'.join(current_command).strip()
        if command:
            commands.append(command)
    
    # Выполняем каждую команду отдельно
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                for i, command in enumerate(commands):
                    try:
                        await conn.execute(text(command))
                        logger.debug(f"Миграция: команда {i + 1}/{len(commands)} выполнена успешно")
                        # Небольшая задержка между командами для избежания конфликтов
                        if i < len(commands) - 1:
                            await asyncio.sleep(0.1)
                    except Exception as cmd_error:
                        error_str = str(cmd_error)
                        # Игнорируем ошибки "уже существует"
                        if any(keyword in error_str.lower() 
                               for keyword in ["already exists", "duplicate", "does not exist", 
                                               "pg_type_typname_nsp_index", "cached plan"]):
                            logger.debug(f"Миграция: команда {i + 1} пропущена (уже применена): {error_str}")
                            continue
                        else:
                            logger.warning(f"Миграция: ошибка в команде {i + 1}: {error_str}")
                            raise
            logger.info(f"Миграция успешно применена ({len(commands)} команд)")
            return
        except Exception as e:
            error_str = str(e)
            # Игнорируем ошибки "уже существует" и "cached plan"
            if any(keyword in error_str.lower() 
                   for keyword in ["already exists", "duplicate", "does not exist", 
                                   "cached plan", "pg_type_typname_nsp_index"]):
                logger.info("Миграция уже применена или объект существует")
                return
            # Если это не последняя попытка, повторяем
            if attempt < max_retries - 1:
                logger.warning(f"Ошибка при применении миграции (попытка {attempt + 1}/{max_retries}): {error_str}. Повтор через {retry_delay}с...")
                await asyncio.sleep(retry_delay)
                continue
            else:
                logger.error(f"Ошибка при применении миграции после {max_retries} попыток: {error_str}")
                raise

