"""
Клиент для взаимодействия с MAX API
"""
import httpx
import logging
from typing import Optional, Dict, Any, List
from services.max_bot_service.config import MAX_API_URL
from services.max_bot_service.utils.stats import stats

logger = logging.getLogger(__name__)


class MaxApiClient:
    """Клиент для работы с MAX API"""
    
    def __init__(self, token: str):
        self.token = token
        self.base_url = MAX_API_URL
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(90.0),  # Увеличенный таймаут для long polling
            headers={"Authorization": token}
        )
    
    async def get_me(self) -> Dict[str, Any]:
        """Получить информацию о боте"""
        try:
            response = await self.client.get(f"{self.base_url}/me")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting bot info: {e}")
            raise
    
    async def get_updates(
        self,
        limit: int = 100,
        timeout: int = 30,
        marker: Optional[int] = None,
        types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Получить обновления через Long Polling
        
        Args:
            limit: Максимальное количество обновлений (1-1000)
            timeout: Таймаут в секундах (0-90)
            marker: Маркер для получения непрочитанных обновлений
            types: Список типов обновлений для фильтрации
        """
        try:
            params = {
                "limit": min(max(limit, 1), 1000),
                "timeout": min(max(timeout, 0), 90)
            }
            
            if marker is not None:
                params["marker"] = marker
            
            if types:
                params["types"] = types
            
            response = await self.client.get(
                f"{self.base_url}/updates",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting updates: {e}")
            raise
    
    async def send_message(
        self,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        text: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        format: Optional[str] = "markdown",
        notify: bool = True,
        disable_link_preview: bool = False
    ) -> Dict[str, Any]:
        """
        Отправить сообщение
        
        Args:
            user_id: ID пользователя (для личных сообщений)
            chat_id: ID чата (для групповых чатов)
            text: Текст сообщения
            attachments: Вложения (клавиатуры, медиа и т.д.)
            format: Формат текста (markdown, html, null)
            notify: Уведомлять ли пользователей
            disable_link_preview: Отключить превью ссылок
        """
        if not user_id and not chat_id:
            raise ValueError("Необходимо указать либо user_id, либо chat_id")
        
        try:
            params = {}
            if user_id:
                params["user_id"] = user_id
            if chat_id:
                params["chat_id"] = chat_id
            if disable_link_preview:
                params["disable_link_preview"] = disable_link_preview
            
            body = {}
            if text is not None:
                body["text"] = text
            if attachments:
                body["attachments"] = attachments
            if format:
                body["format"] = format
            body["notify"] = notify
            
            response = await self.client.post(
                f"{self.base_url}/messages",
                params=params,
                json=body
            )
            response.raise_for_status()
            
            # Записываем статистику
            has_keyboard = bool(attachments and any(
                att.get("type") == "inline_keyboard" for att in attachments
            ))
            stats.record_sent_message(
                message_type="text",
                format=format or "text",
                has_keyboard=has_keyboard
            )
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error sending message: {e}")
            stats.record_error()
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    async def answer_callback(
        self,
        callback_id: str,
        message: Optional[Dict[str, Any]] = None,
        notification: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Ответить на callback (нажатие кнопки)
        
        Args:
            callback_id: ID callback от кнопки
            message: Обновленное сообщение (опционально)
            notification: Одноразовое уведомление (опционально)
        """
        try:
            body = {}
            if message:
                body["message"] = message
            if notification:
                body["notification"] = notification
            
            response = await self.client.post(
                f"{self.base_url}/answers",
                params={"callback_id": callback_id},
                json=body
            )
            response.raise_for_status()
            
            # Записываем статистику callback
            stats.record_callback()
            if message:
                has_keyboard = bool(message.get("attachments") and any(
                    att.get("type") == "inline_keyboard" 
                    for att in message.get("attachments", [])
                ))
                stats.record_sent_message(
                    message_type="callback_response",
                    format=message.get("format", "text"),
                    has_keyboard=has_keyboard
                )
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error answering callback: {e}")
            stats.record_error()
            raise
    
    async def edit_message(
        self,
        message_id: str,
        text: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        format: Optional[str] = "markdown"
    ) -> Dict[str, Any]:
        """
        Редактировать сообщение
        
        Args:
            message_id: ID сообщения для редактирования
            text: Новый текст
            attachments: Новые вложения (None - не изменять, [] - удалить все)
            format: Формат текста
        """
        try:
            body = {}
            if text is not None:
                body["text"] = text
            # Если attachments явно передан (даже пустой список), включаем его в запрос
            # Пустой список удалит все вложения, None - не изменит их
            if attachments is not None:
                body["attachments"] = attachments
            if format:
                body["format"] = format
            
            logger.info(f"Редактирование сообщения {message_id} с телом: {body}")
            
            response = await self.client.put(
                f"{self.base_url}/messages",
                params={"message_id": str(message_id)},
                json=body
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Результат редактирования: {result}")
            return result
        except httpx.HTTPError as e:
            logger.error(f"Error editing message {message_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
                try:
                    error_json = e.response.json()
                    logger.error(f"Response JSON: {error_json}")
                except:
                    pass
            raise
    
    async def delete_message(self, message_id: str) -> Dict[str, Any]:
        """Удалить сообщение"""
        try:
            response = await self.client.delete(
                f"{self.base_url}/messages",
                params={"message_id": message_id}
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error deleting message: {e}")
            raise
    
    async def get_message(self, message_id: str) -> Dict[str, Any]:
        """
        Получить сообщение по ID согласно документации MAX API
        GET /messages/{messageId}
        """
        try:
            response = await self.client.get(
                f"{self.base_url}/messages/{message_id}"
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting message {message_id}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            # Возвращаем пустой словарь вместо raise, чтобы код мог продолжить работу
            return {}
        except Exception as e:
            logger.error(f"Unexpected error getting message {message_id}: {e}")
            return {}
    
    async def get_messages(
        self,
        user_id: Optional[int] = None,
        chat_id: Optional[int] = None,
        limit: int = 100
    ) -> Dict[str, Any]:
        """Получить сообщения из чата"""
        try:
            params = {"limit": limit}
            if user_id:
                params["user_id"] = user_id
            if chat_id:
                params["chat_id"] = chat_id
            
            response = await self.client.get(
                f"{self.base_url}/messages",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting messages: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise
    
    async def get_chats(self) -> Dict[str, Any]:
        """Получить список всех чатов бота"""
        try:
            response = await self.client.get(f"{self.base_url}/chats")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error getting chats: {e}")
            raise
    
    async def set_commands(self, commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Установить команды бота
        
        Args:
            commands: Список команд в формате BotCommand
                     [{"name": "start", "description": "Начать работу с ботом"}, ...]
        
        Returns:
            Результат установки команд
        """
        try:
            # Согласно документации MAX API, команды устанавливаются через PATCH /me
            # с полем commands
            response = await self.client.patch(
                f"{self.base_url}/me",
                json={"commands": commands}
            )
            response.raise_for_status()
            result = response.json()
            logger.info(f"Команды бота успешно установлены: {len(commands)} команд")
            return result
        except httpx.HTTPError as e:
            logger.error(f"Error setting bot commands: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response status: {e.response.status_code}")
                logger.error(f"Response text: {e.response.text}")
            raise
    
    async def close(self):
        """Закрыть соединение"""
        await self.client.aclose()

