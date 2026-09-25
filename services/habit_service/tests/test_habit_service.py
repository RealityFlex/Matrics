"""
Unit тесты для Habit Service
"""
import pytest
from httpx import AsyncClient
from datetime import datetime

from services.test_utils import generate_habit_data


class TestHabitCRUD:
    """Тесты CRUD операций для привычек"""
    
    @pytest.mark.asyncio
    async def test_create_habit(self, client: AsyncClient, sample_user):
        """Создание привычки"""
        habit_data = generate_habit_data(sample_user["id"])
        response = await client.post(f"/habits/?user_id={sample_user['id']}", json=habit_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == habit_data["name"]
        assert data["frequency"] == habit_data["frequency"]
    
    @pytest.mark.asyncio
    async def test_list_habits(self, client: AsyncClient, sample_habit):
        """Список привычек"""
        response = await client.get("/habits/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    @pytest.mark.asyncio
    async def test_get_habit_by_id(self, client: AsyncClient, sample_habit):
        """Получение привычки по ID"""
        response = await client.get(f"/habits/{sample_habit['id']}")
        assert response.status_code == 200
        assert response.json()["id"] == sample_habit["id"]
    
    @pytest.mark.asyncio
    async def test_get_user_habits(self, client: AsyncClient, sample_user, sample_habit):
        """Привычки пользователя"""
        response = await client.get(f"/habits/user/{sample_user['id']}")
        assert response.status_code == 200
        data = response.json()
        assert all(h["user_id"] == sample_user["id"] for h in data)
    
    @pytest.mark.asyncio
    async def test_update_habit(self, client: AsyncClient, sample_habit):
        """Обновление привычки"""
        response = await client.put(
            f"/habits/{sample_habit['id']}",
            json={"name": "Updated Habit"}
        )
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Habit"
    
    @pytest.mark.asyncio
    async def test_delete_habit(self, client: AsyncClient, sample_habit):
        """Удаление привычки"""
        response = await client.delete(f"/habits/{sample_habit['id']}")
        assert response.status_code == 200


class TestHabitLogging:
    """Тесты логирования выполнения привычек"""
    
    @pytest.mark.asyncio
    async def test_log_habit_completion(self, client: AsyncClient, sample_habit, mock_reward_service):
        """Логирование выполнения"""
        response = await client.post(
            f"/habits/{sample_habit['id']}/log",
            json={"notes": "Done today"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "log" in data
        assert "rewards" in data
    
    @pytest.mark.asyncio
    async def test_get_habit_logs(self, client: AsyncClient, sample_habit, mock_reward_service):
        """История выполнений"""
        # Создать несколько логов
        for _ in range(3):
            await client.post(f"/habits/{sample_habit['id']}/log", json={})
        
        response = await client.get(f"/habits/{sample_habit['id']}/logs")
        assert response.status_code == 200
        logs = response.json()
        assert len(logs) >= 3
    
    @pytest.mark.asyncio
    async def test_get_habit_logs_empty(self, client: AsyncClient, sample_habit):
        """Нет выполнений"""
        response = await client.get(f"/habits/{sample_habit['id']}/logs")
        assert response.status_code == 200
        assert response.json() == []


class TestHabitStreaks:
    """Тесты серий выполнения"""
    
    @pytest.mark.asyncio
    async def test_calculate_streak_no_logs(self, client: AsyncClient, sample_habit):
        """Нет серии"""
        response = await client.get(f"/habits/{sample_habit['id']}/streak")
        
        assert response.status_code == 200
        data = response.json()
        assert data["current_streak"] == 0
        assert data["longest_streak"] == 0
    
    @pytest.mark.asyncio
    async def test_habit_calendar_monthly(self, client: AsyncClient, sample_habit, mock_reward_service):
        """Календарь за месяц"""
        # Добавить выполнение
        await client.post(f"/habits/{sample_habit['id']}/log", json={})
        
        now = datetime.now()
        response = await client.get(
            f"/habits/{sample_habit['id']}/calendar?year={now.year}&month={now.month}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "calendar" in data
        assert "total_days" in data


class TestHabitStatistics:
    """Тесты статистики привычек"""
    
    @pytest.mark.asyncio
    async def test_habit_statistics(self, client: AsyncClient, sample_user, sample_habit):
        """Общая статистика"""
        response = await client.get(f"/habits/stats/{sample_user['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert "total_habits" in data
        assert "total_completions" in data
        assert "by_frequency" in data

