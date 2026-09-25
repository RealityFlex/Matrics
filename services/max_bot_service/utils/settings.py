"""
Модуль для управления настройками бота
"""
import json
import os
import logging
from pathlib import Path
from typing import Dict

logger = logging.getLogger(__name__)

# Путь к файлу настроек (в рабочей директории приложения)
SETTINGS_FILE = Path("/app/max_bot_settings.json")

# Настройки по умолчанию
DEFAULT_SETTINGS = {
    "enabled": True  # По умолчанию бот включен
}


class BotSettings:
    """Класс для управления настройками бота"""
    
    def __init__(self):
        self._settings = self._load_settings()
    
    def _load_settings(self) -> Dict:
        """Загрузить настройки из файла"""
        try:
            if SETTINGS_FILE.exists():
                with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                    # Объединяем с настройками по умолчанию
                    return {**DEFAULT_SETTINGS, **settings}
        except Exception as e:
            logger.warning(f"Ошибка загрузки настроек: {e}, используем настройки по умолчанию")
        
        return DEFAULT_SETTINGS.copy()
    
    def _save_settings(self):
        """Сохранить настройки в файл"""
        try:
            # Создаем директорию, если её нет
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self._settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Настройки сохранены: {self._settings}")
        except Exception as e:
            logger.error(f"Ошибка сохранения настроек: {e}", exc_info=True)
            raise
    
    def is_enabled(self) -> bool:
        """Проверить, включен ли бот"""
        # Перезагружаем настройки при каждом обращении для актуальности
        self._settings = self._load_settings()
        return self._settings.get("enabled", True)
    
    def get_settings(self) -> Dict:
        """Получить все настройки"""
        return self._settings.copy()
    
    def update_settings(self, new_settings: Dict):
        """Обновить настройки"""
        self._settings.update(new_settings)
        self._save_settings()
        logger.info(f"Настройки обновлены: {self._settings}")


# Глобальный экземпляр настроек
bot_settings = BotSettings()

