"""
Обработчик текстовых сообщений
"""
import logging
from typing import Dict, Any, Optional
from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.handlers.command_handler import CommandHandler
from services.max_bot_service.utils.stats import stats

logger = logging.getLogger(__name__)


class MessageHandler:
    """Обработчик текстовых сообщений от пользователей"""
    
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
        Обработать сообщение
        
        Args:
            update: Объект обновления с типом message_created
        """
        message = update.get("message", {})
        body = message.get("body", {})
        text = body.get("text", "").strip()
        
        # Логируем структуру сообщения для отладки (только при необходимости)
        logger.debug(f"Полная структура message update: {update}")
        
        # Получаем информацию о пользователе
        sender = message.get("sender", {})
        
        # КРИТИЧНО: Игнорируем сообщения от самого бота
        if sender.get("is_bot", False):
            logger.debug("Игнорируем сообщение от бота")
            return
        
        if not text:
            logger.debug("Получено пустое сообщение")
            return
        
        user_id = sender.get("user_id")
        max_user_name = sender.get("name") or sender.get("username") or sender.get("first_name")

        # Групповой чат учебной группы: только групповые команды, обычные сообщения не комментируем
        from services.max_bot_service.handlers.group_handler import is_group_chat
        if is_group_chat(update):
            if text.startswith("/"):
                await self.command_handler.group.handle_command(update, text)
            return
        
        if not user_id:
            logger.warning("Не удалось получить user_id из сообщения")
            return
        
        # Проверяем, является ли сообщение командой
        if text.startswith("/"):
            command = text.split(maxsplit=1)[0].lower()
            stats.record_received_message(is_command=True, command=command)
            await self.command_handler.handle_command(user_id, text, update, max_user_name=max_user_name)
        else:
            # Обработка обычного текстового сообщения
            stats.record_received_message(is_command=False)
            await self.handle_text_message(user_id, text, update)
    
    async def handle_text_message(
        self,
        user_id: int,
        text: str,
        update: Dict[str, Any]
    ):
        """
        Обработать обычное текстовое сообщение
        
        Args:
            user_id: ID пользователя MAX
            text: Текст сообщения
            update: Полный объект обновления
        """
        message = update.get("message", {})
        body = message.get("body", {})
        
        # Проверяем, является ли сообщение ответом на другое сообщение
        # link может быть в body или на верхнем уровне message
        link = body.get("link")
        if not link:
            link = message.get("link")
        
        # Подробное логирование структуры link для отладки
        logger.debug(f"Полная структура body: {body}")
        logger.debug(f"Полная структура message: {message}")
        if link:
            logger.info(f"Обнаружен link в сообщении: {link}")
            # Согласно документации MAX API, message ID находится в поле 'mid'
            link_message_id = link.get("mid") or link.get("message_id")
            logger.info(f"Извлеченный message_id из link: {link_message_id}")
            if not link_message_id:
                logger.warning(f"Не удалось извлечь message_id из link в message_handler. Структура link: {link}")
        else:
            logger.debug("Link не найден в сообщении (проверены body.link и message.link)")
        
        # Пробуем создать задачу, если это не команда и текст не пустой
        # Это может быть ответ на сообщение о создании задачи
        sender = message.get("sender", {})
        if not sender.get("is_bot") and text and not text.strip().startswith("/"):
            logger.info(f"Попытка создать задачу из текстового сообщения пользователя {user_id}: {text[:50]}...")
            # Пробуем создать задачу из текста
            # Если это ответ на сообщение о создании задачи, задача будет создана
            success = await self.command_handler.handle_task_create_from_reply(user_id, text, update, max_user_name=sender.get("name"))
            if success:
                # Задача создана, не отправляем стандартное сообщение
                logger.info(f"Задача успешно создана из ответа пользователя {user_id}, стандартное сообщение не отправляется")
                return
            else:
                logger.debug(f"Не удалось создать задачу из ответа пользователя {user_id}, отправляем стандартное сообщение")
        
        # По умолчанию отправляем подсказку (только если задача не была создана)
        await self.api_client.send_message(
            user_id=user_id,
            text="Используйте команды для взаимодействия с ботом. Введите /help для списка команд.",
            format="markdown"
        )

