"""
Тесты входа через MAX initData, поиска по MAX id, ролей и защиты сброса БД.
"""
import time
from unittest.mock import patch

import pytest

from services.shared.max_auth import sign_init_data
from services.test_utils import MockServiceClient

TOKEN = "test-bot-token"


def init_data(max_id=777, **user):
    profile = {"id": max_id, "first_name": "Анна", **user}
    return sign_init_data({"auth_date": int(time.time()), "user": profile, "start_param": "att-1-0001"}, TOKEN)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("MAX_BOT_TOKEN", TOKEN)
    mock = MockServiceClient("any")
    mock.get_mock.return_value = []
    with patch("services.user_service.main.ServiceClient", return_value=mock):
        yield


class TestMaxLogin:
    @pytest.mark.asyncio
    async def test_first_login_creates_user_then_reuses(self, client):
        first = await client.post("/users/auth/max", json={"init_data": init_data()})
        assert first.status_code == 200, first.text
        data = first.json()
        assert data["is_new"] is True
        assert data["user"]["email"] == "max_777@max.local"
        assert data["start_param"] == "att-1-0001"

        second = await client.post("/users/auth/max", json={"init_data": init_data()})
        assert second.json()["is_new"] is False
        assert second.json()["user"]["id"] == data["user"]["id"]

        by_max = await client.get("/users/by-max/777")
        assert by_max.status_code == 200 and by_max.json()["id"] == data["user"]["id"]

    @pytest.mark.asyncio
    async def test_username_clash_resolved(self, client):
        await client.post("/users/", json={"username": "Анна", "email": "anna@example.com"})
        response = await client.post("/users/auth/max", json={"init_data": init_data(max_id=888)})
        assert response.status_code == 200
        assert response.json()["user"]["username"] == "Анна_888"

    @pytest.mark.asyncio
    async def test_bad_signature_rejected(self, client):
        tampered = init_data().replace("777", "778")
        response = await client.post("/users/auth/max", json={"init_data": tampered})
        assert response.status_code == 401


class TestAdminAndRoles:
    @pytest.mark.asyncio
    async def test_reset_database_disabled_by_default(self, client):
        response = await client.post("/users/admin/reset-database")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_verify_requires_token(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "adm")
        assert (await client.get("/users/admin/verify")).status_code == 401
        assert (await client.get("/users/admin/verify", headers={"X-Admin-Token": "adm"})).status_code == 200

    @pytest.mark.asyncio
    async def test_assign_curator_role(self, client, sample_user, test_db_session):
        from services.shared.models.social import StudentGroup

        group = StudentGroup(name="ИВТ-11")
        test_db_session.add(group)
        await test_db_session.commit()
        response = await client.put(
            f"/users/{sample_user['id']}/role", json={"role": "curator", "group_ids": [group.id]}
        )
        assert response.status_code == 200, response.text
        assert response.json()["role"] == "curator"
        assert response.json()["curator_group_ids"] == [group.id]
