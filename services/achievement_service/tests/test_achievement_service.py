"""
Unit тесты для Achievement Service
"""
import pytest
from httpx import AsyncClient
from services.test_utils import generate_achievement_data


class TestAchievementCRUD:
    @pytest.mark.asyncio
    async def test_create_achievement(self, client: AsyncClient):
        achievement_data = generate_achievement_data()
        response = await client.post("/achievements/", json=achievement_data)
        assert response.status_code == 201
    
    @pytest.mark.asyncio
    async def test_list_achievements(self, client: AsyncClient, sample_achievement):
        response = await client.get("/achievements/")
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_update_achievement_progress(
        self, client: AsyncClient, sample_user, sample_achievement, mock_reward_service
    ):
        response = await client.post(
            f"/achievements/users/{sample_user['id']}/progress",
            params={"achievement_id": sample_achievement['id'], "increment": 5}
        )
        assert response.status_code == 200


class TestAchievementProgress:
    @pytest.mark.asyncio
    async def test_achievement_completion(
        self, client: AsyncClient, sample_user, sample_achievement, mock_reward_service
    ):
        # Полностью выполнить достижение
        requirement = sample_achievement["requirement_value"]
        response = await client.post(
            f"/achievements/users/{sample_user['id']}/progress",
            params={"achievement_id": sample_achievement['id'], "increment": requirement}
        )
        assert response.status_code == 200
        assert response.json()["completed"] is True

