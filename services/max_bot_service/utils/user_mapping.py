"""
Утилиты для маппинга между внутренним user_id и max_user_id
"""
import logging
import re
from typing import Optional
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


async def get_max_user_id(user_id: int) -> Optional[int]:
    """
    Получить max_user_id из внутреннего user_id
    
    Args:
        user_id: Внутренний ID пользователя
        
    Returns:
        max_user_id или None, если пользователь не найден или не зарегистрирован в MAX
    """
    try:
        user_service = ServiceClient("user")
        user = await user_service.get(f"/users/{user_id}")
        await user_service.close()
        
        if not user:
            return None
        
        email = user.get("email", "")
        # Email имеет формат: max_{max_user_id}@max.local
        match = re.match(r"max_(\d+)@max\.local", email)
        if match:
            return int(match.group(1))
        
        return None
    except Exception as e:
        logger.warning(f"Ошибка при получении max_user_id для user_id={user_id}: {e}")
        return None


async def get_user_id_from_max_id(max_user_id: int) -> Optional[int]:
    """
    Получить внутренний user_id из max_user_id
    
    Args:
        max_user_id: ID пользователя в MAX
        
    Returns:
        Внутренний user_id или None, если пользователь не найден
    """
    try:
        user_service = ServiceClient("user")
        try:
            user = await user_service.get(f"/users/by-max/{max_user_id}")
            if isinstance(user, dict) and user.get("id"):
                return user["id"]
        except Exception:
            pass
        email = f"max_{max_user_id}@max.local"
        
        # Запасной вариант: получаем пользователей и ищем по email
        users = await user_service.get("/users/", params={"limit": 1000})
        await user_service.close()
        
        if isinstance(users, list):
            for user in users:
                if user.get("email") == email:
                    return user.get("id")
        
        return None
    except Exception as e:
        logger.warning(f"Ошибка при получении user_id для max_user_id={max_user_id}: {e}")
        return None

