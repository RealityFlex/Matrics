"""
Утилиты для тестирования микросервисов
"""
from typing import Dict, Any, Optional
from unittest.mock import AsyncMock, MagicMock
from faker import Faker

fake = Faker(['ru_RU'])


class MockServiceClient:
    """
    Мок для ServiceClient для тестирования межсервисного взаимодействия
    """
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.responses: Dict[str, Any] = {}
        self.get_mock = AsyncMock()
        self.post_mock = AsyncMock()
        self.put_mock = AsyncMock()
        self.delete_mock = AsyncMock()
        self.close_mock = AsyncMock()
    
    def set_response(self, endpoint: str, response: Any):
        """Установить ответ для определенного эндпоинта"""
        self.responses[endpoint] = response
    
    async def get(self, url: str, params: Optional[Dict] = None):
        """Мок GET запроса"""
        # Проверить, есть ли заранее настроенный ответ
        for endpoint, response in self.responses.items():
            if endpoint in url:
                return response
        
        # Вызвать мок
        return await self.get_mock(url, params)
    
    async def post(self, url: str, json: Optional[Dict] = None, **kwargs):
        """Мок POST запроса"""
        for endpoint, response in self.responses.items():
            if endpoint in url:
                return response
        
        return await self.post_mock(url, json, **kwargs)
    
    async def put(self, url: str, json: Optional[Dict] = None):
        """Мок PUT запроса"""
        for endpoint, response in self.responses.items():
            if endpoint in url:
                return response
        
        return await self.put_mock(url, json)
    
    async def delete(self, url: str):
        """Мок DELETE запроса"""
        for endpoint, response in self.responses.items():
            if endpoint in url:
                return response
        
        return await self.delete_mock(url)
    
    async def close(self):
        """Мок закрытия соединения"""
        await self.close_mock()


def generate_user_data() -> Dict[str, str]:
    """Генерировать данные тестового пользователя"""
    return {
        "username": fake.user_name(),
        "email": fake.email()
    }


def generate_character_data(user_id: int) -> Dict[str, Any]:
    """Генерировать данные тестового персонажа"""
    return {
        "user_id": user_id,
        "name": fake.first_name(),
        "satisfaction": 50,
        "intelligence_level": 1,
        "intelligence_points": 0,
        "bonus_points": 0
    }


def generate_task_data(user_id: int) -> Dict[str, Any]:
    """Генерировать данные тестовой задачи"""
    return {
        "title": fake.sentence(nb_words=5),
        "description": fake.text(max_nb_chars=200),
        "priority": "medium",  # lowercase to match enum
        "reward_coins": 10,
        "reward_intelligence_points": 5,
        "reward_satisfaction": 5
    }


def generate_habit_data(user_id: int) -> Dict[str, Any]:
    """Генерировать данные тестовой привычки"""
    return {
        "name": fake.sentence(nb_words=3),
        "description": fake.text(max_nb_chars=100),
        "frequency": "daily",  # lowercase to match enum
        "target_count": 1,
        "reward_coins": 5,
        "reward_intelligence_points": 2
    }


def generate_item_data() -> Dict[str, Any]:
    """Генерировать данные тестового предмета"""
    return {
        "name": fake.word().capitalize(),
        "description": fake.text(max_nb_chars=100),
        "rarity": "common",  # lowercase to match enum
        "type": "consumable",  # lowercase to match enum
        "base_price": 100
    }


def generate_achievement_data() -> Dict[str, Any]:
    """Генерировать данные тестового достижения"""
    return {
        "name": fake.sentence(nb_words=3),
        "description": fake.text(max_nb_chars=100),
        "requirement_type": "tasks_completed",
        "requirement_value": 10,
        "reward_coins": 50,
        "reward_intelligence_points": 20,
        "is_hidden": False
    }


def generate_clan_data() -> Dict[str, Any]:
    """Генерировать данные тестового клана"""
    return {
        "name": fake.company(),
        "description": fake.text(max_nb_chars=200),
        "tag": fake.lexify(text='???').upper()
    }


def generate_event_data() -> Dict[str, Any]:
    """Генерировать данные тестового события"""
    from datetime import datetime, timedelta
    
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(hours=2)
    
    return {
        "name": fake.catch_phrase(),
        "description": fake.text(max_nb_chars=200),
        "location": fake.address(),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "max_participants": 100,
        "is_public": True,
        "reward_coins": 20,
        "reward_intelligence_points": 10
    }


def generate_competition_data() -> Dict[str, Any]:
    """Генерировать данные тестового соревнования"""
    from datetime import datetime, timedelta
    
    start_time = datetime.now() + timedelta(days=1)
    end_time = start_time + timedelta(days=7)
    
    return {
        "name": fake.catch_phrase(),
        "description": fake.text(max_nb_chars=200),
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "first_place_coins": 1000,
        "second_place_coins": 500,
        "third_place_coins": 250,
        "is_active": True
    }

