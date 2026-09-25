"""
Скрипт для выдачи стартового предмета всем пользователям через API
"""
import asyncio
import httpx
import sys

API_BASE = "http://localhost/api"

async def get_starter_item(client: httpx.AsyncClient) -> dict:
    """Получить или создать стартовый предмет"""
    # Ищем предмет "Стартовый набор"
    # Пробуем разные пути, так как роутинг может отличаться
    paths_to_try = [
        f"{API_BASE}/inventory/items/",  # Через gateway
        "http://localhost:8005/items/",  # Напрямую к сервису
    ]
    
    for path in paths_to_try:
        try:
            response = await client.get(path)
            response.raise_for_status()
            items = response.json()
            starter_item = next((item for item in items if item.get("name") == "Стартовый набор"), None)
            
            if not starter_item:
                # Создаем стартовый предмет, если его нет
                try:
                    response = await client.post(path, json={
                        "name": "Стартовый набор",
                        "description": "Подарочный набор для новых игроков",
                        "rarity": "common",
                        "type": "special",
                        "base_price": 0
                    })
                    response.raise_for_status()
                    starter_item = response.json()
                    print(f"✅ Создан стартовый предмет: {starter_item['name']} (ID: {starter_item['id']})")
                except httpx.HTTPStatusError as e:
                    print(f"⚠️  Ошибка при создании предмета через {path}: {e.response.status_code}")
                    print(f"   Response: {e.response.text[:200]}")
                    continue
            else:
                print(f"✅ Найден существующий стартовый предмет: {starter_item['name']} (ID: {starter_item['id']})")
            
            return starter_item
        except httpx.HTTPStatusError as e:
            print(f"⚠️  Путь {path} не работает: {e.response.status_code}")
            continue
        except Exception as e:
            print(f"⚠️  Ошибка при обращении к {path}: {e}")
            continue
    
    # Если все пути не сработали, пробуем создать через прямой доступ к сервису
    raise Exception("Не удалось получить или создать стартовый предмет. Проверьте, что inventory-service запущен и доступен.")

async def give_starter_item_to_user(client: httpx.AsyncClient, user_id: int, item_id: int) -> bool:
    """Выдать стартовый предмет пользователю"""
    try:
        response = await client.post(
            f"{API_BASE}/inventory/users/{user_id}/items/add?item_id={item_id}&quantity=1",
            json={}
        )
        response.raise_for_status()
        return True
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 400:
            # Предмет уже есть у пользователя
            return False
        print(f"⚠️  Ошибка при выдаче предмета пользователю {user_id}: {e}")
        return False
    except Exception as e:
        print(f"⚠️  Ошибка при выдаче предмета пользователю {user_id}: {e}")
        return False

async def main():
    """Основная функция"""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            # Получаем или создаем стартовый предмет
            starter_item = await get_starter_item(client)
            
            # Получаем всех пользователей
            response = await client.get(f"{API_BASE}/users/")
            response.raise_for_status()
            users = response.json()
            
            print(f"\n📋 Найдено пользователей: {len(users)}")
            
            if not users:
                print("⚠️  Пользователей не найдено")
                return
            
            # Выдаем предмет всем пользователям
            new_items = 0
            updated_items = 0
            errors = 0
            
            for user in users:
                user_id = user["id"]
                result = await give_starter_item_to_user(client, user_id, starter_item["id"])
                if result:
                    new_items += 1
                else:
                    updated_items += 1
                print(f"   Пользователь {user['username']} (ID: {user_id}): {'✅ Выдан' if result else 'ℹ️  Уже есть'}")
            
            print(f"\n✅ Готово!")
            print(f"   - Выдано новым пользователям: {new_items}")
            print(f"   - Уже было у пользователей: {updated_items}")
            print(f"   - Всего обработано: {len(users)}")
            
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

