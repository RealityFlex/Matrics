"""
Утилиты для межсервисного взаимодействия
"""
import httpx
import logging
from typing import Optional, Dict, Any

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL сервисов
SERVICE_URLS = {
    "user": "http://user-service:8001",
    "character": "http://character-service:8002",
    "task": "http://task-service:8003",
    "habit": "http://habit-service:8004",
    "inventory": "http://inventory-service:8005",
    "achievement": "http://achievement-service:8006",
    "social": "http://social-service:8007",
    "event": "http://event-service:8008",
    "economy": "http://economy-service:8009",
    "competition": "http://competition-service:8010",
    "reward": "http://reward-service:8011",
    "statistics": "http://statistics-service:8012",
    "notification": "http://notification-service:8013",
    "max_bot": "http://max-bot-service:8020",
}


class ServiceClient:
    """
    Клиент для взаимодействия между микросервисами
    """
    
    def __init__(self, service_name: str):
        self.base_url = SERVICE_URLS.get(service_name, "")
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET запрос к другому сервису"""
        try:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"GET {url} with params {params}")
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            raise
    
    async def post(self, endpoint: str, json: Optional[Dict[str, Any]] = None, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """POST запрос к другому сервису"""
        try:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"POST {url} with data {json} and params {params}")
            response = await self.client.post(url, json=json, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            # Извлекаем детали ошибки из ответа
            error_detail = "Неизвестная ошибка"
            try:
                # Пытаемся получить JSON с деталями ошибки
                error_data = e.response.json()
                error_detail = error_data.get("detail", str(error_data))
            except:
                # Если не JSON, пытаемся получить текст
                try:
                    error_detail = e.response.text[:200] if hasattr(e.response, 'text') else str(e)
                except:
                    error_detail = str(e)
            logger.error(f"HTTP error {e.response.status_code} occurred: {error_detail}")
            # Создаем исключение с детальной информацией
            raise Exception(f"HTTP {e.response.status_code}: {error_detail}")
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            raise
    
    async def put(self, endpoint: str, json: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """PUT запрос к другому сервису"""
        try:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"PUT {url} with data {json}")
            response = await self.client.put(url, json=json)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            raise
    
    async def delete(self, endpoint: str) -> Dict[str, Any]:
        """DELETE запрос к другому сервису"""
        try:
            url = f"{self.base_url}{endpoint}"
            logger.info(f"DELETE {url}")
            response = await self.client.delete(url)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"HTTP error occurred: {e}")
            raise
        except Exception as e:
            logger.error(f"Error occurred: {e}")
            raise
    
    async def close(self):
        """Закрыть соединение"""
        await self.client.aclose()

