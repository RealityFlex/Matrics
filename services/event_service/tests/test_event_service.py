"""
Unit тесты для Event Service
"""
import pytest
from httpx import AsyncClient
from services.test_utils import generate_event_data


class TestEventCRUD:
    @pytest.mark.asyncio
    async def test_create_event(self, client: AsyncClient):
        event_data = generate_event_data()
        response = await client.post("/events/", json=event_data)
        assert response.status_code == 201
    
    @pytest.mark.asyncio
    async def test_list_events(self, client: AsyncClient, sample_event):
        response = await client.get("/events/")
        assert response.status_code == 200


class TestEventAttendance:
    @pytest.mark.asyncio
    async def test_register_for_event(self, client: AsyncClient, sample_user, sample_event):
        response = await client.post(
            f"/events/{sample_event['id']}/register",
            params={"user_id": sample_user['id']}
        )
        assert response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_mark_attendance(
        self, client: AsyncClient, sample_user, sample_event, mock_reward_service
    ):
        # Зарегистрироваться
        await client.post(
            f"/events/{sample_event['id']}/register",
            params={"user_id": sample_user['id']}
        )
        # Отметить посещение
        response = await client.post(
            f"/events/{sample_event['id']}/attend",
            params={"user_id": sample_user['id']}
        )
        assert response.status_code == 200

