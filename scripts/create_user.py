"""
Скрипт для создания пользователя в базе данных
"""
import asyncio
import httpx
import json

# Пробуем разные варианты URL
USER_SERVICE_URLS = [
    "http://localhost:8001",
    "http://user-service:8001",
    "http://127.0.0.1:8001"
]


async def find_user_by_email(email: str, url: str) -> dict:
    """Найти пользователя по email"""
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            # Получаем всех пользователей и ищем по email
            response = await client.get(f"{url}/users/", params={"limit": 10000})
            response.raise_for_status()
            users = response.json()
            if isinstance(users, list):
                for user in users:
                    if user.get("email") == email:
                        return user
            return None
        except Exception as e:
            print(f"   Ошибка при поиске пользователя: {e}")
            return None


async def create_user(username: str, email: str):
    """Создать пользователя или показать существующего"""
    last_error = None
    for url in USER_SERVICE_URLS:
        try:
            print(f"Попытка подключения к {url}...")
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Проверяем доступность сервиса
                try:
                    health = await client.get(f"{url}/health")
                    if health.status_code != 200:
                        continue
                except:
                    print(f"   Сервис недоступен по адресу {url}")
                    continue
                
                print(f"   Сервис доступен, проверяем существование пользователя...")
                
                # Сначала проверяем, существует ли пользователь
                existing_user = await find_user_by_email(email, url)
                if existing_user:
                    print(f"✅ Пользователь уже существует:")
                    print(f"   ID: {existing_user.get('id')}")
                    print(f"   Username: {existing_user.get('username')}")
                    print(f"   Email: {existing_user.get('email')}")
                    print(f"   Монеты: {existing_user.get('coins', 0)}")
                    return existing_user
                
                print(f"   Пользователь не найден, создаем нового...")
                response = await client.post(
                    f"{url}/users/",
                    json={
                        "username": username,
                        "email": email
                    }
                )
                response.raise_for_status()
                user = response.json()
                print(f"✅ Пользователь успешно создан:")
                print(f"   ID: {user.get('id')}")
                print(f"   Username: {user.get('username')}")
                print(f"   Email: {user.get('email')}")
                print(f"   Монеты: {user.get('coins', 0)}")
                return user
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 400:
                error_detail = e.response.json().get("detail", "Неизвестная ошибка")
                print(f"❌ Ошибка: {error_detail}")
                if "уже зарегистрирован" in error_detail or "уже занят" in error_detail:
                    print(f"   Пользователь с такими данными уже существует")
                    # Пробуем найти существующего пользователя
                    existing_user = await find_user_by_email(email, url)
                    if existing_user:
                        print(f"✅ Найден существующий пользователь:")
                        print(f"   ID: {existing_user.get('id')}")
                        print(f"   Username: {existing_user.get('username')}")
                        print(f"   Email: {existing_user.get('email')}")
                        print(f"   Монеты: {existing_user.get('coins', 0)}")
                        return existing_user
                return None
            else:
                last_error = f"HTTP {e.response.status_code}: {e.response.text}"
        except Exception as e:
            last_error = str(e)
            continue
    
    print(f"❌ Не удалось создать пользователя. Последняя ошибка: {last_error}")
    print(f"   Проверьте, что user-service запущен и доступен")
    return None


if __name__ == "__main__":
    # Создаем пользователя
    asyncio.run(create_user("Александр", "max_42804319@max.local"))

