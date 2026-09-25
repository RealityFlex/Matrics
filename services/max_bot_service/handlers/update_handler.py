"""
Главный обработчик обновлений от MAX API
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any
from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.handlers.message_handler import MessageHandler
from services.max_bot_service.handlers.callback_handler import CallbackHandler
from services.max_bot_service.handlers.command_handler import CommandHandler
from services.max_bot_service.config import LONG_POLLING_TIMEOUT
from services.max_bot_service.utils.settings import bot_settings

logger = logging.getLogger(__name__)


class UpdateHandler:
    """Обработчик обновлений от MAX API"""
    
    def __init__(self, api_client: MaxApiClient):
        self.api_client = api_client
        # Создаем один общий экземпляр CommandHandler для обоих обработчиков
        # чтобы состояние users_awaiting_task_title было общим
        self.command_handler = CommandHandler(api_client)
        self.message_handler = MessageHandler(api_client, self.command_handler)
        self.callback_handler = CallbackHandler(api_client, self.command_handler)
        self.marker: Optional[int] = None
        self.running = False
        # Дедупликация обновлений: храним уникальные идентификаторы обработанных обновлений
        # Формат: {update_id: timestamp}
        self.processed_updates: Dict[str, float] = {}
        # Время жизни записей о обработанных обновлениях (1 час)
        self.update_ttl = 3600
        # Время запуска бота - игнорируем сообщения, созданные до запуска
        self.start_time: Optional[float] = None
    
    async def start_long_polling(self):
        """Запустить Long Polling в бесконечном цикле"""
        self.running = True
        # Запоминаем время запуска - игнорируем сообщения, созданные до этого момента
        self.start_time = time.time()
        logger.info("Запуск Long Polling...")
        
        # Получаем информацию о боте для проверки подключения
        try:
            bot_info = await self.api_client.get_me()
            logger.info(f"Бот подключен: {bot_info.get('name', 'Unknown')}")
        except Exception as e:
            logger.error(f"Ошибка подключения к MAX API: {e}")
            return
        
        # При первом запуске получаем текущий marker, чтобы не обрабатывать старые сообщения
        if self.marker is None:
            logger.info("Первый запуск: получаем текущий marker для пропуска старых сообщений")
            try:
                # Делаем несколько попыток получить текущий marker
                # Используем timeout=0 для немедленного ответа без ожидания новых обновлений
                initial_updates = await self.api_client.get_updates(
                    timeout=0,
                    limit=100
                )
                initial_marker = initial_updates.get("marker")
                if initial_marker:
                    self.marker = initial_marker
                    logger.info(f"Установлен начальный marker: {self.marker}")
                    # Пропускаем все полученные обновления - они старые
                    updates_count = len(initial_updates.get("updates", []))
                    if updates_count > 0:
                        logger.info(f"Пропущено {updates_count} старых обновлений при инициализации")
                else:
                    # Если marker не получен, делаем еще одну попытку с timeout=1
                    logger.warning("Marker не получен в первом запросе, делаем повторную попытку...")
                    initial_updates = await self.api_client.get_updates(
                        timeout=1,
                        limit=1
                    )
                    initial_marker = initial_updates.get("marker")
                    if initial_marker:
                        self.marker = initial_marker
                        logger.info(f"Установлен начальный marker (повторная попытка): {self.marker}")
                    else:
                        logger.warning("Не удалось получить marker. Будем игнорировать все сообщения, созданные до запуска бота.")
            except Exception as e:
                logger.warning(f"Не удалось получить начальный marker: {e}. Будем игнорировать все сообщения, созданные до запуска бота.")
        
        while self.running:
            try:
                # Получаем обновления
                updates_data = await self.api_client.get_updates(
                    timeout=LONG_POLLING_TIMEOUT,
                    marker=self.marker
                )
                
                updates = updates_data.get("updates", [])
                new_marker = updates_data.get("marker")
                
                if new_marker:
                    self.marker = new_marker
                
                # Обрабатываем каждое обновление
                if updates:
                    logger.debug(f"Получено {len(updates)} обновлений, marker: {self.marker}")
                for update in updates:
                    await self.handle_update(update)
                
            except asyncio.CancelledError:
                logger.info("Long Polling остановлен")
                break
            except Exception as e:
                logger.error(f"Ошибка при получении обновлений: {e}")
                # Небольшая задержка перед повтором
                await asyncio.sleep(5)
    
    def _get_update_id(self, update: Dict[str, Any]) -> Optional[str]:
        """
        Извлечь уникальный идентификатор обновления для дедупликации
        
        Args:
            update: Объект обновления от MAX API
            
        Returns:
            Уникальный идентификатор обновления или None
        """
        update_type = update.get("update_type")
        
        if update_type == "message_created":
            # Для сообщений используем message.body.mid
            message = update.get("message", {})
            body = message.get("body", {})
            message_id = body.get("mid")
            if message_id:
                return f"msg_{message_id}"
        elif update_type == "message_callback":
            # Для коллбэков используем callback.callback_id (он уникален)
            callback = update.get("callback", {})
            callback_id = callback.get("callback_id")
            if callback_id:
                return f"cb_{callback_id}"
        elif update_type == "bot_started":
            user = update.get("user") or {}
            return f"start_{user.get('user_id')}_{update.get('timestamp')}_{update.get('payload')}"
        elif update_type == "bot_added":
            return f"added_{update.get('chat_id')}_{update.get('timestamp')}"
        
        return None
    
    def _cleanup_old_updates(self):
        """Очистить старые записи о обработанных обновлениях"""
        current_time = time.time()
        # Удаляем записи старше TTL
        expired_ids = [
            update_id for update_id, timestamp in self.processed_updates.items()
            if current_time - timestamp > self.update_ttl
        ]
        for update_id in expired_ids:
            del self.processed_updates[update_id]
        
        if expired_ids:
            logger.debug(f"Очищено {len(expired_ids)} старых записей о обновлениях")
    
    def _is_message_too_old(self, update: Dict[str, Any]) -> bool:
        """
        Проверить, не слишком ли старое сообщение
        
        Args:
            update: Объект обновления от MAX API
            
        Returns:
            True, если сообщение слишком старое (создано до запуска бота)
        """
        if self.start_time is None:
            return False
        
        update_type = update.get("update_type")
        if update_type == "message_created":
            message = update.get("message", {})
            # Пытаемся получить время создания сообщения
            # В MAX API время может быть в разных полях
            created_at = message.get("created_at") or message.get("timestamp")
            if created_at:
                # Если это строка, пытаемся распарсить
                if isinstance(created_at, str):
                    try:
                        from datetime import datetime
                        msg_time = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                        msg_timestamp = msg_time.timestamp()
                        # Игнорируем ВСЕ сообщения, созданные до запуска бота (без буфера в 5 минут)
                        # Это гарантирует, что мы не обработаем старые сообщения из истории
                        if msg_timestamp < self.start_time:
                            logger.debug(f"Игнорируем старое сообщение: создано {msg_timestamp}, бот запущен {self.start_time}")
                            return True
                    except Exception as e:
                        logger.debug(f"Ошибка парсинга времени сообщения: {e}")
                        pass
                elif isinstance(created_at, (int, float)):
                    # Если это timestamp
                    # Игнорируем ВСЕ сообщения, созданные до запуска бота
                    if created_at < self.start_time:
                        logger.debug(f"Игнорируем старое сообщение: создано {created_at}, бот запущен {self.start_time}")
                        return True
            else:
                # Если время создания недоступно, но marker не установлен,
                # лучше пропустить сообщение, чтобы не обработать старые сообщения
                if self.marker is None:
                    logger.debug("Время создания недоступно и marker не установлен - пропускаем сообщение")
                    return True
        
        return False
    
    async def handle_update(self, update: Dict[str, Any]):
        """
        Обработать одно обновление
        
        Args:
            update: Объект обновления от MAX API
        """
        # Проверяем, включен ли бот
        if not bot_settings.is_enabled():
            logger.debug("Бот выключен, игнорируем обновление")
            return
        
        # Игнорируем слишком старые сообщения (созданные до запуска бота)
        if self._is_message_too_old(update):
            logger.debug("Игнорируем старое сообщение (создано до запуска бота)")
            return
        
        # Извлекаем уникальный идентификатор обновления
        update_id = self._get_update_id(update)
        
        # Проверяем дедупликацию
        current_time = time.time()
        
        # Периодически очищаем старые записи (каждые 100 обновлений)
        if len(self.processed_updates) % 100 == 0:
            self._cleanup_old_updates()
        
        if update_id:
            # Проверяем, не обрабатывали ли мы это обновление ранее
            if update_id in self.processed_updates:
                logger.debug(f"Пропущено дублирующее обновление: {update_id}")
                return
            
            # Сохраняем идентификатор обработанного обновления
            self.processed_updates[update_id] = current_time
        else:
            # Если не удалось извлечь идентификатор, используем комбинацию типа и времени
            # Это не идеально, но лучше, чем обрабатывать обновление несколько раз
            update_type = update.get("update_type", "unknown")
            fallback_id = f"{update_type}_{current_time}_{id(update)}"
            if fallback_id in self.processed_updates:
                logger.debug(f"Пропущено обновление без ID (fallback): {update_type}")
                return
            self.processed_updates[fallback_id] = current_time
            logger.warning(f"Не удалось извлечь идентификатор обновления {update_type}, используется fallback ID")
        
        update_type = update.get("update_type")
        
        try:
            if update_type == "message_created":
                await self.message_handler.handle(update)
            elif update_type == "message_callback":
                await self.callback_handler.handle(update)
            elif update_type == "bot_started":
                await self.command_handler.handle_bot_started(update)
            elif update_type == "bot_added":
                await self.command_handler.group.handle_bot_added(update)
            elif update_type == "message_edited":
                logger.debug(f"Сообщение отредактировано: {update}")
            elif update_type == "message_deleted":
                logger.debug(f"Сообщение удалено: {update}")
            else:
                logger.debug(f"Неизвестный тип обновления: {update_type}")
        except Exception as e:
            logger.error(f"Ошибка обработки обновления {update_type}: {e}")
            # В случае ошибки не удаляем update_id из processed_updates,
            # чтобы не обрабатывать проблемное обновление повторно

