"""
Сервис для работы с персонажами
"""
import logging
from typing import Optional, Dict, Any
import httpx
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


class CharacterService:
    """Сервис для работы с персонажами"""
    
    def __init__(self):
        self.service_client = ServiceClient("character")
    
    async def get_character(self, user_id: int, max_user_id: Optional[int] = None, max_user_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Получить персонажа пользователя. Если персонажа нет, создает его автоматически.
        
        Args:
            user_id: ID пользователя (внутренний)
            max_user_id: ID пользователя в MAX (опционально)
            max_user_name: Имя пользователя в MAX (опционально)
        
        Returns:
            Информация о персонаже
        """
        try:
            character = await self.service_client.get(f"/characters/user/{user_id}")
            return character
        except httpx.HTTPStatusError as e:
            # Если персонаж не найден (404), создаем его
            if e.response.status_code == 404:
                logger.info(f"Персонаж не найден для пользователя {user_id}, создаем нового")
                try:
                    # Формируем имя персонажа
                    if max_user_name:
                        character_name = max_user_name
                    elif max_user_id:
                        character_name = f"Пользователь {max_user_id}"
                    else:
                        character_name = f"Персонаж {user_id}"
                    
                    character = await self.create_character(user_id, character_name, max_user_id=max_user_id)
                    return character
                except httpx.HTTPStatusError as create_error:
                    # Если персонаж уже существует (400), получаем его снова
                    if create_error.response.status_code == 400:
                        logger.info(f"Персонаж уже существует, получаем его")
                        try:
                            character = await self.service_client.get(f"/characters/user/{user_id}")
                            return character
                        except:
                            pass
                    logger.error(f"Ошибка создания персонажа: {create_error}")
                    return None
                except Exception as create_error:
                    logger.error(f"Ошибка создания персонажа: {create_error}")
                    return None
            else:
                logger.error(f"Ошибка получения персонажа (статус {e.response.status_code}): {e}")
                return None
        except Exception as e:
            # Обработка других типов ошибок
            error_str = str(e).lower()
            if "404" in error_str or "не найден" in error_str or "not found" in error_str:
                logger.info(f"Персонаж не найден для пользователя {user_id}, создаем нового")
                try:
                    # Формируем имя персонажа
                    if max_user_name:
                        character_name = max_user_name
                    elif max_user_id:
                        character_name = f"Пользователь {max_user_id}"
                    else:
                        character_name = f"Персонаж {user_id}"
                    
                    character = await self.create_character(user_id, character_name, max_user_id=max_user_id)
                    return character
                except Exception as create_error:
                    logger.error(f"Ошибка создания персонажа: {create_error}")
                    return None
            else:
                logger.error(f"Ошибка получения персонажа: {e}")
                return None
    
    async def create_character(self, user_id: int, name: str, max_user_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Создать персонажа для пользователя
        
        Args:
            user_id: ID пользователя (внутренний)
            name: Имя персонажа
            max_user_id: ID пользователя в MAX (опционально, для сохранения связи)
        """
        character_data = {"user_id": user_id, "name": name}
        if max_user_id:
            character_data["max_user_id"] = max_user_id
        
        return await self.service_client.post(
            "/characters/",
            json=character_data
        )
    
    async def update_character(self, character_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        """Обновить персонажа"""
        return await self.service_client.put(
            f"/characters/{character_id}",
            json=data
        )
    
    async def close(self):
        """Закрыть соединение"""
        await self.service_client.close()

