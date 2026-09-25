"""
Конфигурация для MAX Bot Service
"""
import os
from dotenv import load_dotenv

load_dotenv()

# Токен бота MAX (обязательная переменная)
MAX_BOT_TOKEN = os.getenv("MAX_BOT_TOKEN")
if not MAX_BOT_TOKEN:
    raise ValueError("MAX_BOT_TOKEN не установлен в переменных окружения")

# URL API MAX
MAX_API_URL = os.getenv("MAX_API_URL", "https://platform-api.max.ru")

# Таймаут для Long Polling (секунды)
LONG_POLLING_TIMEOUT = int(os.getenv("LONG_POLLING_TIMEOUT", "30"))

# URL базы данных
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не установлен в переменных окружения")


# Ник бота (без @) — для диплинков https://max.ru/<ник>?startapp=...
MAX_BOT_USERNAME = os.getenv("MAX_BOT_USERNAME", "").strip().lstrip("@")

# Публичный HTTPS-адрес мини-приложения (запасной вариант кнопки, если ник бота не задан)
WEBAPP_URL = os.getenv("WEBAPP_URL", "").strip()

# Формат кнопки открытия мини-приложения:
#   link     — ссылка https://max.ru/<бот>?startapp=... (проверенный формат, по умолчанию)
#   open_app — нативная кнопка open_app (включать после проверки на устройстве)
MAX_OPEN_APP_MODE = os.getenv("MAX_OPEN_APP_MODE", "link").strip().lower()
