"""
Unit тесты для Statistics Service
"""
import pytest
from httpx import AsyncClient


class TestUserStatistics:
    @pytest.mark.asyncio
    async def test_get_user_summary_statistics(
        self, client: AsyncClient, sample_user, mock_services
    ):
        response = await client.get(f"/stats/users/{sample_user['id']}/summary")
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_user['id']
    
    @pytest.mark.asyncio
    async def test_get_user_detailed_statistics(
        self, client: AsyncClient, sample_user, mock_services
    ):
        response = await client.get(f"/stats/users/{sample_user['id']}/detailed")
        assert response.status_code == 200


class TestGlobalStatistics:
    @pytest.mark.asyncio
    async def test_get_global_overview(self, client: AsyncClient, mock_services):
        response = await client.get("/stats/global/overview")
        assert response.status_code == 200

