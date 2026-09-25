"""
Модуль для сбора статистики по сообщениям бота
"""
import logging
from typing import Dict
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)


class MessageStats:
    """Класс для сбора статистики по сообщениям"""
    
    def __init__(self):
        self.total_sent = 0
        self.total_received = 0
        self.by_type: Dict[str, int] = defaultdict(int)
        self.by_command: Dict[str, int] = defaultdict(int)
        self.by_format: Dict[str, int] = defaultdict(int)
        self.errors = 0
        self.callbacks = 0
        self.start_time = datetime.now()
    
    def record_sent_message(self, message_type: str = "text", format: str = "text", has_keyboard: bool = False):
        """Записать отправленное сообщение"""
        self.total_sent += 1
        self.by_type[message_type] += 1
        self.by_format[format] += 1
        if has_keyboard:
            self.by_type["with_keyboard"] += 1
        
        logger.info(f"STATS: Отправлено сообщение. Тип: {message_type}, Формат: {format}, Всего: {self.total_sent}")
    
    def record_received_message(self, is_command: bool = False, command: str = None):
        """Записать полученное сообщение"""
        self.total_received += 1
        if is_command and command:
            self.by_command[command] += 1
            logger.info(f"STATS: Получено сообщение. Команда: {command}, Всего: {self.total_received}")
        else:
            logger.info(f"STATS: Получено сообщение. Команда: false, Всего: {self.total_received}")
    
    def record_callback(self):
        """Записать callback (нажатие кнопки)"""
        self.callbacks += 1
        logger.info(f"STATS: Callback. Всего: {self.callbacks}")
    
    def record_error(self):
        """Записать ошибку"""
        self.errors += 1
        logger.warning(f"STATS: Ошибка. Всего: {self.errors}")
    
    def get_stats(self) -> Dict:
        """Получить статистику"""
        uptime = (datetime.now() - self.start_time).total_seconds()
        return {
            "total_sent": self.total_sent,
            "total_received": self.total_received,
            "total_callbacks": self.callbacks,
            "total_errors": self.errors,
            "by_type": dict(self.by_type),
            "by_command": dict(self.by_command),
            "by_format": dict(self.by_format),
            "uptime_seconds": int(uptime),
            "messages_per_minute": round(self.total_sent / (uptime / 60), 2) if uptime > 0 else 0
        }
    
    def reset(self):
        """Сбросить статистику"""
        self.total_sent = 0
        self.total_received = 0
        self.by_type.clear()
        self.by_command.clear()
        self.by_format.clear()
        self.errors = 0
        self.callbacks = 0
        self.start_time = datetime.now()


# Глобальный экземпляр статистики
stats = MessageStats()

