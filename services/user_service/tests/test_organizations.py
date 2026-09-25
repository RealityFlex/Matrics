"""
Тесты подключения организации, вступления по ссылке и привязки чата группы.
"""
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from services.shared.models.appearance import AppearanceSet
from services.shared.models.social import GroupMember, StudentGroup, group_curators
from services.shared.models.user import User
from services.test_utils import MockServiceClient


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("MAX_BOT_USERNAME", "matrix_bot")
    mock = MockServiceClient("any")
    mock.get_mock.return_value = []
    with patch("services.user_service.main.ServiceClient", return_value=mock):
        yield


ONBOARD = {
    "name": "Казанский колледж информатики",
    "short_name": "ККИ",
    "city": "Казань",
    "brand_color": "#1E5BA8",
    "groups": [{"name": "ИС-11"}, {"name": "ИС-12", "team_goal_percent": 70}],
}


class TestOnboarding:
    @pytest.mark.asyncio
    async def test_onboard_creates_groups_links_and_brand(self, client, test_db_session):
        response = await client.post("/users/organizations/onboard", json=ONBOARD)
        assert response.status_code == 201, response.text
        data = response.json()
        assert [g["name"] for g in data["groups"]] == ["ИС-11", "ИС-12"]
        group = data["groups"][0]
        assert group["student_link"] == f"https://max.ru/matrix_bot?startapp=join-{group['invite_code']}"
        assert group["curator_link"].startswith("https://max.ru/matrix_bot?startapp=cur-")
        assert group["bind_chat_command"] == f"/bindgroup {group['curator_code']}"
        brand = (await test_db_session.execute(select(AppearanceSet).where(AppearanceSet.organization_id == data["id"]))).scalar_one()
        assert brand.asset_key == "environment:brand" and brand.theme_id == "#1E5BA8"

        again = await client.post("/users/organizations/onboard", json=ONBOARD)
        assert again.status_code == 400

        listing = await client.get("/users/organizations")
        assert listing.status_code == 200 and listing.json()[0]["name"] == ONBOARD["name"]

    @pytest.mark.asyncio
    async def test_onboard_requires_admin(self, client, monkeypatch):
        monkeypatch.setenv("ADMIN_TOKEN", "adm")
        assert (await client.post("/users/organizations/onboard", json=ONBOARD)).status_code == 401


class TestJoin:
    @pytest.mark.asyncio
    async def test_student_and_curator_join(self, client, test_db_session, sample_user):
        org = (await client.post("/users/organizations/onboard", json=ONBOARD)).json()
        group = org["groups"][0]
        uid = sample_user["id"]

        joined = await client.post(f"/users/join?user_id={uid}", json={"code": f"join-{group['invite_code']}"})
        assert joined.status_code == 200 and joined.json()["kind"] == "student"
        assert joined.json()["organization"]["short_name"] == "ККИ"
        twice = await client.post(f"/users/join?user_id={uid}", json={"code": group["invite_code"]})
        assert twice.json()["already"] is True
        members = (await test_db_session.execute(select(GroupMember).where(GroupMember.user_id == uid))).scalars().all()
        assert len(members) == 1

        curator = await client.post("/users/internal/join", json={"user_id": uid, "code": f"cur-{group['curator_code']}"})
        assert curator.json()["kind"] == "curator"
        user = (await test_db_session.execute(select(User).where(User.id == uid))).scalar_one()
        await test_db_session.refresh(user)
        assert user.role == "curator"

        bad = await client.post(f"/users/join?user_id={uid}", json={"code": "join-NOPE0000"})
        assert bad.status_code == 404

    @pytest.mark.asyncio
    async def test_bind_chat_requires_curator_code(self, client):
        org = (await client.post("/users/organizations/onboard", json=ONBOARD)).json()
        group = org["groups"][1]
        wrong = await client.post("/users/internal/groups/bind-chat", json={"code": group["invite_code"], "chat_id": -42})
        assert wrong.status_code == 404  # студенческий код не даёт привязать чат
        ok = await client.post("/users/internal/groups/bind-chat", json={"code": group["curator_code"], "chat_id": -42})
        assert ok.status_code == 200 and ok.json()["team_goal_percent"] == 70
        info = await client.get("/users/internal/groups/by-chat/-42")
        assert info.json()["group_name"] == "ИС-12"

    @pytest.mark.asyncio
    async def test_app_config(self, client):
        data = (await client.get("/users/app-config")).json()
        assert data["bot_username"] == "matrix_bot" and data["bot_link"] == "https://max.ru/matrix_bot"
