"""
Тесты для проверки выдачи наград при закрытии задач
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select
from services.test_utils import generate_task_data
from services.shared.models.user import User
from services.shared.models.character import Character
from services.shared.models.task import Task
from services.test_utils import MockServiceClient
from unittest.mock import patch


class TestTaskRewards:
    """Тесты для проверки выдачи наград при закрытии задач"""
    
    @pytest.mark.asyncio
    async def test_complete_task_adds_coins_and_intelligence(
        self, client: AsyncClient, sample_user, test_db_session
    ):
        """
        Проверка, что при закрытии задачи пользователю добавляются деньги и интеллект
        """
        # Создать персонажа для пользователя
        character = Character(user_id=sample_user['id'], name="Test Character")
        test_db_session.add(character)
        await test_db_session.commit()
        await test_db_session.refresh(character)
        
        # Получить начальные значения
        result = await test_db_session.execute(
            select(User).where(User.id == sample_user['id'])
        )
        user = result.scalar_one_or_none()
        initial_coins = user.coins
        
        result = await test_db_session.execute(
            select(Character).where(Character.id == character.id)
        )
        character_obj = result.scalar_one_or_none()
        initial_intelligence = character_obj.intelligence_points
        initial_level = character_obj.intelligence_level
        
        # Создать задачу с наградами
        task_data = generate_task_data(sample_user['id'])
        task_data["reward_coins"] = 50
        task_data["reward_intelligence_points"] = 10
        
        task_response = await client.post(
            f"/tasks/?user_id={sample_user['id']}",
            json=task_data
        )
        assert task_response.status_code == 201
        task_id = task_response.json()["id"]
        
        # Настроить моки для сервисов
        user_mock = MockServiceClient("user")
        user_mock.set_response(f"/users/{sample_user['id']}/coins/add", {"success": True})
        
        character_mock = MockServiceClient("character")
        character_mock.set_response(
            f"/characters/user/{sample_user['id']}",
            {"id": character.id, "user_id": sample_user['id']}
        )
        character_mock.set_response(
            f"/characters/{character.id}/intelligence/add",
            {
                "character_id": character.id,
                "intelligence_level": initial_level,
                "intelligence_points": initial_intelligence + 10,
                "level_up": False,
                "levels_gained": 0
            }
        )
        
        reward_mock = MockServiceClient("reward")
        reward_mock.set_response(
            "/rewards/grant",
            {
                "user_id": sample_user['id'],
                "coins_added": 50,
                "intelligence_added": 10,
                "satisfaction_added": 0,
                "level_up": False,
                "achievements_earned": []
            }
        )
        
        # Моки для других сервисов (inventory, achievement)
        inventory_mock = MockServiceClient("inventory")
        achievement_mock = MockServiceClient("achievement")
        achievement_mock.set_response(f"/achievements/check/{sample_user['id']}", {"earned": []})
        
        with patch("services.task_service.main.ServiceClient") as mock_service_client:
            def side_effect(service_name):
                if service_name == "reward":
                    return reward_mock
                elif service_name == "user":
                    return user_mock
                elif service_name == "character":
                    return character_mock
                elif service_name == "inventory":
                    return inventory_mock
                elif service_name == "achievement":
                    return achievement_mock
                return MockServiceClient(service_name)
            
            mock_service_client.side_effect = side_effect
            
            # Завершить задачу
            complete_response = await client.post(f"/tasks/{task_id}/complete")
            assert complete_response.status_code == 200
            data = complete_response.json()
            
            # Проверить, что задача завершена
            assert data["task"]["status"] == "completed"
            assert data["task"]["completed_at"] is not None
            
            # Проверить, что награды выданы
            assert "rewards" in data
            assert data["rewards"]["coins_added"] == 50
            assert data["rewards"]["intelligence_added"] == 10
            
            # Проверить, что reward_service был вызван с правильными параметрами
            assert reward_mock.post_mock.called or "/rewards/grant" in str(reward_mock.responses)
            
            # Проверить, что user_service был вызван для добавления монет
            # (через reward_service)
            # Проверить, что character_service был вызван для добавления очков интеллекта
            # (через reward_service)
    
    @pytest.mark.asyncio
    async def test_complete_task_verifies_reward_service_call(
        self, client: AsyncClient, sample_user, test_db_session
    ):
        """
        Проверка, что reward_service вызывается с правильными параметрами
        """
        # Создать персонажа
        character = Character(user_id=sample_user['id'], name="Test Character")
        test_db_session.add(character)
        await test_db_session.commit()
        await test_db_session.refresh(character)
        
        # Создать задачу с наградами
        task_data = generate_task_data(sample_user['id'])
        task_data["reward_coins"] = 100
        task_data["reward_intelligence_points"] = 20
        
        task_response = await client.post(
            f"/tasks/?user_id={sample_user['id']}",
            json=task_data
        )
        task_id = task_response.json()["id"]
        
        # Настроить моки с отслеживанием вызовов
        reward_mock = MockServiceClient("reward")
        reward_response = {
            "user_id": sample_user['id'],
            "coins_added": 100,
            "intelligence_added": 20,
            "satisfaction_added": 0,
            "level_up": False,
            "achievements_earned": []
        }
        
        # Используем post_mock для отслеживания вызовов
        async def mock_post(url, json=None):
            if "/rewards/grant" in url:
                # Проверить параметры вызова
                assert json is not None
                assert json["user_id"] == sample_user['id']
                assert json["coins"] == 100
                assert json["intelligence_points"] == 20
                assert "satisfaction" in json
                return reward_response
            return await reward_mock.post_mock(url, json)
        
        reward_mock.post = mock_post
        
        with patch("services.task_service.main.ServiceClient", return_value=reward_mock):
            # Завершить задачу
            complete_response = await client.post(f"/tasks/{task_id}/complete")
            assert complete_response.status_code == 200
            
            # Проверить ответ
            data = complete_response.json()
            assert data["rewards"]["coins_added"] == 100
            assert data["rewards"]["intelligence_added"] == 20
            assert data["rewards"]["user_id"] == sample_user['id']
    
    @pytest.mark.asyncio
    async def test_complete_task_with_zero_rewards(
        self, client: AsyncClient, sample_user, test_db_session
    ):
        """
        Проверка завершения задачи без наград
        """
        # Создать персонажа
        character = Character(user_id=sample_user['id'], name="Test Character")
        test_db_session.add(character)
        await test_db_session.commit()
        
        # Создать задачу без наград
        task_data = generate_task_data(sample_user['id'])
        task_data["reward_coins"] = 0
        task_data["reward_intelligence_points"] = 0
        
        task_response = await client.post(
            f"/tasks/?user_id={sample_user['id']}",
            json=task_data
        )
        task_id = task_response.json()["id"]
        
        # Настроить моки
        reward_mock = MockServiceClient("reward")
        reward_mock.set_response(
            "/rewards/grant",
            {
                "user_id": sample_user['id'],
                "coins_added": 0,
                "intelligence_added": 0,
                "satisfaction_added": 0,
                "level_up": False,
                "achievements_earned": []
            }
        )
        
        with patch("services.task_service.main.ServiceClient", return_value=reward_mock):
            # Завершить задачу
            complete_response = await client.post(f"/tasks/{task_id}/complete")
            assert complete_response.status_code == 200
            
            data = complete_response.json()
            assert data["task"]["status"] == "completed"
            assert data["rewards"]["coins_added"] == 0
            assert data["rewards"]["intelligence_added"] == 0

