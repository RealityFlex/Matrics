"""
User Service - Управление пользователями
Порт: 8001
"""
import asyncio
import random
import logging
import re
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text
from typing import List

from services.shared.database import get_db, init_db, engine, Base, AsyncSessionLocal
from services.shared.models.user import User
# Импортируем TaskGeneration для корректной инициализации relationship в User
from services.shared.models.task_generation import TaskGeneration
# Импортируем все модели для корректной работы drop_all
from services.shared.models import (
    Character, Task, Goal, Habit, Item, Achievement,
    Clan, Event, Lesson, ShopListing, Competition
)
from services.shared.utils import ServiceClient
from services.shared.realtime import push_parameters_update
from services.shared.auth import require_admin
from services.shared.migrations import apply_hackathon_migrations

# Импортируем парсер стандартных предметов
import sys
sys.path.append('/app')
from scripts.import_standard_items import get_items_from_directory

# Настройка логирования
logger = logging.getLogger(__name__)

# Pydantic схемы
class UserCreate(BaseModel):
    username: str
    email: str
    
    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Валидация username - не может быть пустым"""
        if not v or not v.strip():
            raise ValueError('Username не может быть пустым')
        return v
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str) -> str:
        """Валидация email формата (разрешаем .local домены для тестирования)"""
        # Проверяем базовый формат email: user@domain
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Некорректный формат email адреса')
        return v

class UserUpdate(BaseModel):
    username: str | None = None
    email: str | None = None
    coins: int | None = None
    
    @field_validator('email')
    @classmethod
    def validate_email(cls, v: str | None) -> str | None:
        """Валидация email формата (разрешаем .local домены для тестирования)"""
        if v is None:
            return v
        # Проверяем базовый формат email: user@domain
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Некорректный формат email адреса')
        return v

class UserResponse(BaseModel):
    id: int
    username: str
    email: str
    coins: int
    role: str = "student"
    
    class Config:
        from_attributes = True

# FastAPI приложение
app = FastAPI(title="User Service", version="1.0.0")

# Фоновая задача для проверки обновления ежедневного приза
DAILY_REWARD_CHECK_INTERVAL_SECONDS = 60 * 60  # Проверка каждый час
_last_notified_day: str | None = None
_daily_reward_check_task: asyncio.Task | None = None


async def _check_and_notify_daily_reward_update():
    """
    Проверяет начало нового дня и отправляет уведомления всем пользователям об обновлении ежедневного приза
    """
    global _last_notified_day
    
    # Первая проверка произойдет сразу после запуска
    while True:
        try:
            current_time = datetime.now(timezone.utc)
            today_start = _start_of_day(current_time)
            today_str = today_start.isoformat()
            
            # Проверяем, не отправляли ли уже уведомление сегодня
            if _last_notified_day == today_str:
                await asyncio.sleep(DAILY_REWARD_CHECK_INTERVAL_SECONDS)
                continue
            
            # Начался новый день - отправляем уведомления
            # Получаем id пользователей и сразу закрываем сессию:
            # рассылка по HTTP не должна держать транзакцию и блокировки таблицы users
            async with AsyncSessionLocal() as session:
                user_ids = list((await session.execute(select(User.id))).scalars().all())

            if user_ids:
                bot_service = ServiceClient("max_bot")
                try:
                    sent_count = 0
                    for user_id in user_ids:
                        try:
                            await bot_service.post("/notifications/daily-reward-updated", json={
                                "user_id": user_id
                            })
                            sent_count += 1
                        except Exception as e:
                            logger.warning(f"Не удалось отправить уведомление об обновлении ежедневного приза пользователю {user_id}: {e}")

                    if sent_count:
                        _last_notified_day = today_str
                        logger.info(f"Отправлено уведомлений об обновлении ежедневного приза: {sent_count}")
                    else:
                        # Бот ещё не запущен или недоступен — повторим на следующей проверке
                        logger.warning("Бот недоступен, уведомления о ежедневном призе будут отправлены позже")
                finally:
                    await bot_service.close()
            else:
                _last_notified_day = today_str  # Отмечаем день даже если пользователей нет
            
            # Ждём перед следующей проверкой
            await asyncio.sleep(DAILY_REWARD_CHECK_INTERVAL_SECONDS)
                    
        except asyncio.CancelledError:
            logger.info("Остановка фоновой задачи проверки обновления ежедневного приза")
            raise
        except Exception as exc:
            logger.exception(f"Ошибка при проверке обновления ежедневного приза: {exc}")
            await asyncio.sleep(60)  # Ждём минуту перед повтором при ошибке


@app.on_event("startup")
async def startup():
    """Инициализация БД при запуске"""
    await init_db()
    await apply_hackathon_migrations()
    # Каталог стандартных предметов на чистой установке (лутбоксы, стартовые предметы, магазин)
    try:
        from services.user_service.catalog_seed import seed_standard_items

        async with AsyncSessionLocal() as session:
            await seed_standard_items(session)
    except Exception as exc:
        logger.warning(f"Каталог предметов не заполнен: {exc}")
    global _daily_reward_check_task
    if _daily_reward_check_task is None or _daily_reward_check_task.done():
        _daily_reward_check_task = asyncio.create_task(_check_and_notify_daily_reward_update())
        logger.info("Фоновая задача проверки обновления ежедневного приза запущена")


@app.on_event("shutdown")
async def shutdown():
    """Остановка фоновых задач при выключении"""
    global _daily_reward_check_task
    if _daily_reward_check_task is not None:
        _daily_reward_check_task.cancel()
        try:
            await _daily_reward_check_task
        except asyncio.CancelledError:
            pass
        _daily_reward_check_task = None
        logger.info("Фоновая задача проверки обновления ежедневного приза остановлена")

# Вход через MAX, роли пользователей
from services.user_service import max_login, organizations  # noqa: E402

app.include_router(max_login.router)
app.include_router(organizations.router)

@app.get("/")
async def root():
    return {"service": "User Service", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

# CRUD эндпоинты
@app.post("/users/", response_model=UserResponse, status_code=201)
async def create_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Создать нового пользователя"""
    # Проверка уникальности email
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    
    # Проверка уникальности username
    result = await db.execute(select(User).where(User.username == user_in.username))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username уже занят")
    
    user = User(**user_in.model_dump())
    db.add(user)
    
    # КЛЮЧЕВОЕ ИСПРАВЛЕНИЕ: коммитим транзакцию перед вызовом других сервисов
    # Это гарантирует, что пользователь будет виден в БД для inventory-service
    try:
        await db.commit()
        await db.refresh(user)
    except Exception as e:
        await db.rollback()
        logger.error(f"Ошибка создания пользователя: {str(e)}")
        raise HTTPException(status_code=500, detail="Ошибка сохранения пользователя")
    
    # Выдаем три рандомных стартовых предмета новому пользователю
    try:
        inventory_service = ServiceClient("inventory")
        try:
            # Получаем все предметы
            items = await inventory_service.get("/items/")
            logger.info(f"Получено предметов из инвентаря: {len(items) if items else 0}")
            
            if items and len(items) > 0:
                # Выбираем три рандомных РАЗНЫХ предмета (random.sample гарантирует уникальность)
                # Если предметов меньше 3, берем все доступные
                num_items_to_give = min(3, len(items))
                random_items = random.sample(items, num_items_to_give)
                logger.info(f"Выбрано {num_items_to_give} предметов для выдачи пользователю {user.id}: {[item.get('name', item.get('id')) for item in random_items]}")
                
                # Выдаем каждый предмет пользователю (каждый предмет будет в отдельном стаке, так как они разные)
                given_count = 0
                for item in random_items:
                    try:
                        await inventory_service.post(
                            f"/items/add-to-user/{user.id}",
                            params={"item_id": item['id'], "quantity": 1}
                        )
                        given_count += 1
                        logger.info(f"✅ Выдан предмет '{item.get('name', item.get('id'))}' пользователю {user.id}")
                    except Exception as e:
                        # Логируем ошибку для конкретного предмета, но продолжаем
                        logger.warning(f"❌ Не удалось выдать предмет {item.get('name', item.get('id'))} пользователю {user.id}: {e}")
                
                if given_count > 0:
                    logger.info(f"✅ Успешно выдано {given_count} из {num_items_to_give} стартовых предметов пользователю {user.id}")
                else:
                    logger.warning(f"⚠️ Не удалось выдать ни одного предмета пользователю {user.id}")
            else:
                # Если предметов нет, логируем предупреждение
                logger.warning(f"⚠️ Нет доступных предметов для выдачи новому пользователю {user.id}")
        except Exception as e:
            # Логируем ошибку, но не прерываем создание пользователя
            logger.warning(f"❌ Не удалось выдать стартовые предметы пользователю {user.id}: {e}", exc_info=True)
        finally:
            await inventory_service.close()
    except Exception as e:
        # Если сервис недоступен, просто логируем
        logger.warning(f"❌ Сервис инвентаря недоступен при создании пользователя {user.id}: {e}")
    
    # Автоматически создаем базового персонажа
    try:
        character_service = ServiceClient("character")
        try:
            await character_service.post(
                "/characters/",
                json={
                    "user_id": user.id,
                    "name": f"Персонаж {user.username}",
                    "satisfaction": 50,
                    "intelligence_level": 1,
                    "intelligence_points": 0,
                    "bonus_points": 0
                }
            )
        except HTTPException as e:
            if e.status_code == 400:
                logger.warning(f"Персонаж для пользователя {user.id} уже существует, пропускаем создание")
            else:
                logger.warning(f"Не удалось создать персонажа для пользователя {user.id}: {e.detail}")
        except Exception as e:
            logger.warning(f"Не удалось создать персонажа для пользователя {user.id}: {e}")
        finally:
            await character_service.close()
    except Exception as e:
        logger.warning(f"Сервис персонажей недоступен при создании пользователя: {e}")

    return user

@app.get("/users/", response_model=List[UserResponse])
async def list_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """Получить список пользователей"""
    result = await db.execute(select(User).offset(skip).limit(limit))
    return result.scalars().all()

@app.post("/users/admin/reset-database", dependencies=[Depends(require_admin)])
async def reset_database():
    """
    ⚠️ ОПАСНО: Сносит всю базу данных и создает начальные данные
    Удаляет все таблицы, создает их заново и добавляет 5 предметов + 1 достижение.
    Доступно только администратору и только при ALLOW_DB_RESET=true.
    """
    if os.getenv("ALLOW_DB_RESET", "false").strip().lower() not in {"1", "true", "yes"}:
        raise HTTPException(status_code=403, detail="Сброс базы отключён (ALLOW_DB_RESET=false)")
    try:
        logger.warning("Начало сноса базы данных...")
        
        # Сначала завершаем все активные соединения к БД (кроме текущего)
        # Это необходимо для освобождения блокировок
        try:
            async with engine.begin() as conn:
                # Завершаем все активные соединения, кроме системных и текущего
                await conn.execute(
                    text("SELECT pg_terminate_backend(pid) "
                         "FROM pg_stat_activity "
                         "WHERE datname = current_database() "
                         "AND pid != pg_backend_pid() "
                         "AND state != 'idle'")
                )
                logger.info("Завершены активные соединения к БД")
                # Небольшая задержка для освобождения блокировок
                await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"Не удалось завершить активные соединения (это может быть нормально): {e}")
        
        # Удаляем все таблицы с повторными попытками
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with engine.begin() as conn:
                    # Используем CASCADE для принудительного удаления зависимостей
                    await conn.run_sync(Base.metadata.drop_all)
                    logger.info("Все таблицы удалены")
                    break
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Ошибка при удалении таблиц (попытка {attempt + 1}/{max_retries}): {e}. Повтор через 2с...")
                    await asyncio.sleep(2)
                    # Снова пытаемся завершить соединения
                    try:
                        async with engine.begin() as conn:
                            await conn.execute(
                                text("SELECT pg_terminate_backend(pid) "
                                     "FROM pg_stat_activity "
                                     "WHERE datname = current_database() "
                                     "AND pid != pg_backend_pid() "
                                     "AND state != 'idle'")
                            )
                            await asyncio.sleep(1)
                    except:
                        pass
                else:
                    logger.error(f"Не удалось удалить таблицы после {max_retries} попыток: {e}")
                    raise
        
        # Создаем таблицы заново
        await init_db()
        logger.info("Таблицы созданы заново")
        
        # Инвалидируем кэш планов PostgreSQL после изменения структуры БД
        try:
            async with engine.begin() as conn:
                await conn.execute(text("DISCARD PLANS"))
                logger.info("Кэш планов PostgreSQL инвалидирован")
        except Exception as e:
            logger.warning(f"Не удалось инвалидировать кэш планов (это может быть нормально): {e}")
        
        # Небольшая задержка для стабилизации БД
        await asyncio.sleep(0.5)
        
        # Создаем начальные данные через сервисы
        inventory_client = ServiceClient("inventory")
        achievement_client = ServiceClient("achievement")
        
        # Импорт стандартных предметов из папки standard_items
        logger.info("🎨 Импортируем стандартные предметы...")
        standard_items_path = Path("/app/scripts/standard_items")
        
        # Проверяем существование директории
        if not standard_items_path.exists():
            logger.error(f"❌ Директория {standard_items_path} не существует!")
            raise HTTPException(
                status_code=500, 
                detail=f"Директория стандартных предметов не найдена: {standard_items_path}"
            )
        
        logger.info(f"📁 Путь к стандартным предметам: {standard_items_path}")
        logger.info(f"📁 Директория существует: {standard_items_path.exists()}")
        
        # Создаем директорию для хранения изображений предметов, если её нет
        images_dir = Path("/app/static/items")
        images_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"📁 Директория для изображений: {images_dir}")
        
        # Получаем список предметов из папки
        logger.info(f"🔍 Сканируем директорию {standard_items_path}...")
        
        # Пробуем вывести содержимое директории для диагностики перед вызовом функции
        try:
            files_in_dir = list(standard_items_path.iterdir())
            logger.info(f"📂 Файлов в директории: {len(files_in_dir)}")
            image_files = [f for f in files_in_dir if f.is_file() and f.suffix.lower() in {'.png', '.jpg', '.jpeg', '.webp', '.gif'}]
            logger.info(f"🖼️ Изображений в директории: {len(image_files)}")
            for f in image_files[:10]:  # Показываем первые 10 файлов
                logger.info(f"   - {f.name}")
        except Exception as e:
            logger.error(f"❌ Ошибка при чтении директории: {e}")
        
        items_from_files = get_items_from_directory(str(standard_items_path))
        logger.info(f"📦 Найдено предметов для импорта: {len(items_from_files)}")
        
        if len(items_from_files) == 0:
            logger.warning(f"⚠️ В директории {standard_items_path} не найдено предметов для импорта!")
            logger.warning(f"⚠️ Возможные причины:")
            logger.warning(f"   1. Директория пуста")
            logger.warning(f"   2. Файлы не соответствуют формату имени (РЕДКОСТЬ_НАЗВАНИЕ_[награды].png)")
            logger.warning(f"   3. Файлы не являются изображениями (.png, .jpg, .jpeg, .webp, .gif)")
            # Продолжаем выполнение, но без предметов
        
        created_items = []
        failed_items = []
        
        # Импортируем предметы (если они есть)
        for idx, item_file_data in enumerate(items_from_files, 1):
            try:
                logger.info(f"📦 [{idx}/{len(items_from_files)}] Обрабатываем: {item_file_data.get('name', 'unknown')}")
                
                # Копируем изображение в static директорию (для резервного копирования)
                source_image = Path(item_file_data['file_path'])
                dest_image = images_dir / source_image.name
                shutil.copy2(source_image, dest_image)
                
                # Формируем данные для создания предмета
                item_data = {
                    "name": item_file_data['name'],
                    "description": f"Редкость: {item_file_data['rarity']}",
                    "rarity": item_file_data['rarity'],
                    "type": "consumable",  # Все стандартные предметы - расходуемые
                    "base_price": item_file_data.get('coins', 0),
                    "reward_coins": item_file_data.get('coins', 0),
                    "reward_intelligence_points": item_file_data.get('intelligence_points', 0),
                    "reward_satisfaction": item_file_data.get('satisfaction', 0),
                    "image_filename": source_image.name,
                    "image_data": item_file_data.get('image_base64')  # Сохраняем base64 в БД
                }
                
                # Создаем предмет через API
                item = await inventory_client.post("/items/", json=item_data)
                created_items.append(item)
                logger.info(f"✅ [{idx}/{len(items_from_files)}] Создан: {item_data['name']}")
                
            except Exception as e:
                failed_items.append(item_file_data['name'])
                logger.error(f"❌ [{idx}/{len(items_from_files)}] Ошибка при создании предмета '{item_file_data['name']}': {str(e)}")
        
        # Итоговый отчет
        logger.info(f"📊 Создано предметов: {len(created_items)} из {len(items_from_files)}")
        if failed_items:
            logger.warning(f"⚠️ Не удалось создать {len(failed_items)} предметов: {', '.join(failed_items[:5])}")
        else:
            logger.info(f"✅ Успешно импортированы все стандартные предметы в базу данных")
        
        # 1 достижение
        achievement_data = {
            "name": "Первый шаг",
            "description": "Добро пожаловать в игру!",
            "requirement_type": "tasks_completed",
            "requirement_value": 1,
            "reward_coins": 100,
            "reward_intelligence_points": 10,
            "is_hidden": False
        }
        
        try:
            achievement = await achievement_client.post("/achievements/", json=achievement_data)
            logger.info(f"Создано достижение: {achievement_data['name']}")
        except Exception as e:
            logger.error(f"Ошибка создания достижения: {e}")
            achievement = None
        
        # Закрываем клиенты
        await inventory_client.close()
        await achievement_client.close()
        
        result_message = {
            "message": "База данных успешно снесена и пересоздана",
            "created_items": len(created_items),
            "expected_items": 5,
            "created_achievements": 1 if achievement else 0,
            "items_status": "success" if len(created_items) == 5 else "partial"
        }
        
        if failed_items:
            result_message["failed_items"] = failed_items
        
        if len(created_items) != 5:
            logger.warning(f"⚠️ Создано только {len(created_items)} из 5 предметов!")
            result_message["warning"] = f"Создано только {len(created_items)} из 5 предметов"
        
        return result_message
    except Exception as e:
        logger.error(f"Ошибка при сносе базы данных: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка при сносе базы данных: {str(e)}")

@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(user_id: int, user_in: UserUpdate, db: AsyncSession = Depends(get_db)):
    """Обновить пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    update_data = user_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)
    
    await db.commit()
    await db.refresh(user)

    if "coins" in update_data:
        await push_parameters_update(
            user.id,
            coins=user.coins,
            source="user_service.update_user",
        )

    return user

@app.delete("/users/{user_id}", response_model=UserResponse)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Удалить пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    await db.delete(user)
    await db.commit()
    return user

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получить пользователя по ID"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return user

# Дополнительные эндпоинты
@app.get("/users/{user_id}/coins")
async def get_user_coins(user_id: int, db: AsyncSession = Depends(get_db)):
    """Получить количество монет пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return {"user_id": user.id, "coins": user.coins}

class CoinsAddRequest(BaseModel):
    amount: int
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: int) -> int:
        """Валидация количества монет - должно быть неотрицательным"""
        if v < 0:
            raise ValueError('Количество монет должно быть неотрицательным')
        return v

@app.post("/users/{user_id}/coins/add")
async def add_coins(user_id: int, request: CoinsAddRequest, db: AsyncSession = Depends(get_db)):
    """Добавить монеты пользователю"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    user.coins += request.amount
    await db.commit()
    await db.refresh(user)

    await push_parameters_update(
        user.id,
        coins=user.coins,
        source="user_service.add_coins",
        metadata={"delta": request.amount},
    )

    return {"user_id": user.id, "coins": user.coins, "added": request.amount}

class CoinsSubtractRequest(BaseModel):
    amount: int
    
    @field_validator('amount')
    @classmethod
    def validate_amount(cls, v: int) -> int:
        """Валидация amount - должен быть положительным"""
        if v <= 0:
            raise ValueError('Количество монет должно быть положительным')
        return v

@app.post("/users/{user_id}/coins/subtract")
async def subtract_coins(
    user_id: int, 
    request: CoinsSubtractRequest,
    db: AsyncSession = Depends(get_db)
):
    """Списать монеты у пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    if user.coins < request.amount:
        raise HTTPException(status_code=400, detail="Недостаточно монет")
    
    user.coins -= request.amount
    await db.commit()
    await db.refresh(user)

    await push_parameters_update(
        user.id,
        coins=user.coins,
        source="user_service.subtract_coins",
        metadata={"delta": -request.amount},
    )

    return {"user_id": user.id, "coins": user.coins, "subtracted": request.amount}

def _start_of_day(dt: datetime) -> datetime:
    dt_utc = dt.astimezone(timezone.utc)
    return datetime(dt_utc.year, dt_utc.month, dt_utc.day, tzinfo=timezone.utc)

class DailyRewardResponse(BaseModel):
    success: bool
    coins_added: int
    claimed_at: datetime | None
    next_available_at: datetime

@app.get("/users/{user_id}/daily-reward", response_model=DailyRewardResponse)
async def get_daily_reward_status(user_id: int, db: AsyncSession = Depends(get_db)):
    """Проверить доступность ежедневного приза для пользователя"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    now = datetime.now(timezone.utc)
    today_start = _start_of_day(now)
    next_available = today_start + timedelta(days=1)
    last_claim = user.last_daily_reward_at

    # Если подарок еще не получали сегодня (или вообще никогда), он доступен
    is_available = not last_claim or last_claim < today_start

    return DailyRewardResponse(
        success=is_available,
        coins_added=0,
        claimed_at=last_claim,
        next_available_at=next_available
    )

@app.post("/users/{user_id}/daily-reward", response_model=DailyRewardResponse)
async def claim_daily_reward(user_id: int, db: AsyncSession = Depends(get_db)):
    """Выдать ежедневный приз пользователю (10 монет раз в сутки)."""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    now = datetime.now(timezone.utc)
    today_start = _start_of_day(now)
    next_available = today_start + timedelta(days=1)
    last_claim = user.last_daily_reward_at

    # Если подарок уже получен сегодня, возвращаем информацию об этом
    if last_claim and last_claim >= today_start:
        return DailyRewardResponse(
            success=False,
            coins_added=0,
            claimed_at=last_claim,
            next_available_at=next_available
        )

    # Выдаем подарок (включая первый раз, когда last_claim == None)
    user.coins += 10
    user.last_daily_reward_at = now
    await db.commit()
    await db.refresh(user)

    await push_parameters_update(
        user.id,
        coins=user.coins,
        source="user_service.daily_reward",
        metadata={"reward": 10},
    )

    return DailyRewardResponse(
        success=True,
        coins_added=10,
        claimed_at=user.last_daily_reward_at,
        next_available_at=next_available
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)