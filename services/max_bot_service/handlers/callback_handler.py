"""
Обработчик callback от нажатий на кнопки
"""
import logging
from typing import Dict, Any, Optional
from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.handlers.command_handler import CommandHandler

logger = logging.getLogger(__name__)


class CallbackHandler:
    """Обработчик callback от inline-кнопок"""
    
    def __init__(self, api_client: MaxApiClient, command_handler: Optional[CommandHandler] = None):
        self.api_client = api_client
        # Используем переданный command_handler или создаем новый
        # Это позволяет использовать один общий экземпляр для сохранения состояния
        if command_handler is None:
            self.command_handler = CommandHandler(api_client)
        else:
            self.command_handler = command_handler
    
    async def handle(self, update: Dict[str, Any]):
        """
        Обработать callback
        
        Args:
            update: Объект обновления с типом message_callback
        """
        # Логируем полную структуру update для отладки
        logger.info(f"Полная структура callback update: {update}")
        
        callback = update.get("callback", {})
        callback_id = callback.get("callback_id")
        payload = callback.get("payload", "")
        user = callback.get("user", {})
        user_id = user.get("user_id")
        
        # Проверяем наличие message - он находится на верхнем уровне update, а не в callback
        message = update.get("message", {})
        if message:
            # message_id находится в body.mid
            body = message.get("body", {})
            message_id = body.get("mid")
            logger.info(f"Message ID из update.message.body.mid: {message_id}")
        else:
            logger.warning("Message не найден в update объекте")
        
        if not user_id or not callback_id:
            logger.warning("Не удалось получить user_id или callback_id из callback")
            return
        
        logger.info(f"Callback от пользователя {user_id}: {payload}")
        
        # Обрабатываем payload как команду
        await self.command_handler.handle_callback(user_id, payload, callback_id, update)

