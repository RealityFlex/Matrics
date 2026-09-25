"""
Unit тесты для Reward Service
"""
import pytest
from httpx import AsyncClient


class TestRewardGrant:
    @pytest.mark.asyncio
    async def test_grant_rewards_coins_only(self, client: AsyncClient, sample_user, mock_services):
        response = await client.post(
            "/rewards/grant",
            json={"user_id": sample_user['id'], "coins": 50}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["coins_added"] == 50
        assert data["satisfaction_added"] == 0
    
    @pytest.mark.asyncio
    async def test_grant_rewards_intelligence_only(
        self, client: AsyncClient, sample_user, mock_services
    ):
        response = await client.post(
            "/rewards/grant",
            json={"user_id": sample_user['id'], "intelligence_points": 20}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["intelligence_added"] == 20
        assert data["satisfaction_added"] == 0

    @pytest.mark.asyncio
    async def test_grant_rewards_satisfaction_only(
        self, client: AsyncClient, sample_user, mock_services
    ):
        response = await client.post(
            "/rewards/grant",
            json={"user_id": sample_user['id'], "satisfaction": 15}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction_added"] == 15
    
    @pytest.mark.asyncio
    async def test_grant_rewards_combined(self, client: AsyncClient, sample_user, mock_services):
        response = await client.post(
            "/rewards/grant",
            json={
                "user_id": sample_user['id'],
                "coins": 100,
                "intelligence_points": 50,
                "satisfaction": 12,
                "item_id": 1,
                "item_quantity": 2
            }
        )
        assert response.status_code == 200



class TestRewardLedger:
    @pytest.mark.asyncio
    async def test_reward_written_to_ledger_with_source(
        self, client: AsyncClient, sample_user, mock_services, test_db_session
    ):
        from sqlalchemy import select
        from services.shared.models.economy import Transaction

        response = await client.post(
            "/rewards/grant",
            json={
                "user_id": sample_user["id"],
                "coins": 5,
                "intelligence_points": 10,
                "satisfaction": 5,
                "source": "lesson_attendance",
                "source_ref": "lesson:1",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction_added"] == 5
        assert data["character"] is not None

        rows = (await test_db_session.execute(
            select(Transaction).where(Transaction.user_id == sample_user["id"])
        )).scalars().all()
        assert len(rows) == 1
        assert rows[0].source == "lesson_attendance"
        assert rows[0].source_ref == "lesson:1"
        assert rows[0].amount == 5
