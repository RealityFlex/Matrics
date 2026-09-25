"""
Скрипт для выдачи трёх случайных предметов всем пользователям через API
"""
import asyncio
import sys
import os
import random
import httpx

# URL сервисов (можно изменить для локального запуска)
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8005")
USER_SERVICE_URL = os.getenv("USER_SERVICE_URL", "http://localhost:8001")

async def get_all_items() -> list:
    """Получить все предметы из инвентаря"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{INVENTORY_SERVICE_URL}/items/")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка получения предметов: {e}")
            return []

async def get_all_users() -> list:
    """Получить всех пользователей"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.get(f"{USER_SERVICE_URL}/users/")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"❌ Ошибка получения пользователей: {e}")
            return []

async def add_item_to_user(user_id: int, item_id: int) -> bool:
    """Добавить предмет пользователю"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                f"{INVENTORY_SERVICE_URL}/items/add-to-user/{user_id}",
                params={"item_id": item_id, "quantity": 1}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"   ⚠️  Ошибка добавления предмета {item_id}: {e}")
            return False

async def give_random_items_to_user(user_id: int, items: list) -> int:
    """Выдать три случайных разных предмета пользователю"""
    if not items or len(items) < 3:
        print(f"⚠️  Недостаточно предметов (нужно минимум 3, найдено {len(items) if items else 0})")
        return 0
    
    # Выбираем три случайных разных предмета
    random_items = random.sample(items, 3)
    
    added_count = 0
    for item in random_items:
        if await add_item_to_user(user_id, item['id']):
            added_count += 1
    
    return added_count

async def main():
    """Основная функция"""
    print("🔄 Загрузка данных...")
    
    # Получаем все предметы и пользователей
    items = await get_all_items()
    users = await get_all_users()
    
    print(f"📦 Найдено предметов: {len(items)}")
    print(f"👥 Найдено пользователей: {len(users)}")
    
    if not items or len(items) < 3:
        print("❌ Недостаточно предметов в базе (нужно минимум 3)")
        return
    
    if not users:
        print("⚠️  Пользователей не найдено")
        return
    
    print(f"\n🔄 Выдача трёх случайных предметов каждому пользователю...\n")
    
    # Выдаем три случайных предмета каждому пользователю
    total_added = 0
    users_processed = 0
    
    for user in users:
        try:
            added = await give_random_items_to_user(user['id'], items)
            total_added += added
            users_processed += 1
            print(f"✅ {user['username']} (ID: {user['id']}): выдано {added} предметов")
        except Exception as e:
            print(f"❌ Ошибка для пользователя {user['username']} (ID: {user['id']}): {e}")
    
    print(f"\n✅ Готово!")
    print(f"   - Обработано пользователей: {users_processed}")
    print(f"   - Всего выдано предметов: {total_added}")
    print(f"   - Среднее предметов на пользователя: {total_added / users_processed if users_processed > 0 else 0:.1f}")

if __name__ == "__main__":
    asyncio.run(main())

