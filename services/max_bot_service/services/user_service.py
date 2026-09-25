"""
Сервис для работы с пользователями
"""
import logging
from typing import Optional, Dict, Any
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


class UserService:
    """Сервис для работы с пользователями"""
    
    def __init__(self):
        self.service_client = ServiceClient("user")
        self.inventory_client = ServiceClient("inventory")
        self.achievement_client = ServiceClient("achievement")
    
    async def get_or_create_user(self, max_user_id: int, max_user_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Получить или создать пользователя по MAX user_id
        
        Args:
            max_user_id: ID пользователя в MAX
            max_user_name: Имя пользователя в MAX (опционально)
        
        Returns:
            Информация о пользователе
        """
        # Создаем уникальный email для пользователя MAX
        email = f"max_{max_user_id}@max.local"
        # Используем имя пользователя из MAX, если доступно, иначе генерируем
        if max_user_name:
            username = max_user_name
        else:
            username = f"max_user_{max_user_id}"
        
        # Быстрый поиск по MAX id (user-service: GET /users/by-max/{id})
        try:
            return await self.service_client.get(f"/users/by-max/{max_user_id}")
        except Exception:
            pass  # 404 — пользователь ещё не создан; ошибки сети — пробуем старый способ

        # Запасной вариант: перебор списка пользователей
        try:
            # Получаем всех пользователей и ищем по email
            users = await self.service_client.get("/users/", params={"limit": 1000})
            if isinstance(users, list):
                for user in users:
                    if user.get("email") == email:
                        return user
        except Exception as e:
            logger.warning(f"Ошибка при поиске пользователя: {e}")
        
        # Пользователь не найден, создаем нового
        try:
            new_user = await self.service_client.post(
                "/users/",
                json={
                    "username": username,
                    "email": email
                }
            )
            return new_user
        except Exception as e:
            # Если пользователь уже существует (race condition), пытаемся получить его
            logger.warning(f"Пользователь уже существует, получаем его: {e}")
            try:
                users = await self.service_client.get("/users/", params={"limit": 1000})
                if isinstance(users, list):
                    for user in users:
                        if user.get("email") == email:
                            # Если имя пользователя изменилось и мы знаем новое имя, обновляем его
                            if max_user_name and user.get("username") != max_user_name:
                                try:
                                    updated_user = await self.service_client.put(
                                        f"/users/{user.get('id')}",
                                        json={"username": max_user_name}
                                    )
                                    return updated_user
                                except Exception as update_error:
                                    logger.warning(f"Не удалось обновить имя пользователя: {update_error}")
                            return user
            except:
                pass
            # Если не удалось найти, пробуем создать с другим username
            username = f"max_user_{max_user_id}_{max_user_id}"
            return await self.service_client.post(
                "/users/",
                json={
                    "username": username,
                    "email": email
                }
            )
    
    async def get_user(self, user_id: int) -> Dict[str, Any]:
        """Получить пользователя по ID"""
        return await self.service_client.get(f"/users/{user_id}")
    
    async def get_inventory(self, user_id: int) -> Dict[str, Any]:
        """Получить инвентарь пользователя"""
        try:
            items = await self.inventory_client.get(f"/inventory/users/{user_id}")
            if isinstance(items, list):
                return {"items": items}
            return {"items": []}
        except Exception as e:
            logger.error(f"Ошибка получения инвентаря: {e}")
            return {"items": []}
    
    async def get_achievements(self, user_id: int) -> Dict[str, Any]:
        """Получить достижения пользователя"""
        try:
            achievements = await self.achievement_client.get(f"/achievements/users/{user_id}")
            if isinstance(achievements, list):
                return {"achievements": achievements}
            return {"achievements": []}
        except Exception as e:
            logger.error(f"Ошибка получения достижений: {e}")
            return {"achievements": []}
    
    async def close(self):
        """Закрыть соединения"""
        await self.service_client.close()
        await self.inventory_client.close()
        await self.achievement_client.close()

