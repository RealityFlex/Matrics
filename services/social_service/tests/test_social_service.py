"""
Unit тесты для Social Service - Социальные взаимодействия
"""
import pytest
from httpx import AsyncClient
from services.test_utils import generate_user_data, generate_clan_data
from services.shared.models.user import User
from services.shared.models.social import ClanRole, FriendshipStatus


class TestClanFeatures:
    """Тесты для кланов"""
    
    @pytest.mark.asyncio
    async def test_create_clan(self, client: AsyncClient, sample_user):
        """Создание клана"""
        clan_data = generate_clan_data()
        response = await client.post(
            "/clans/",
            params={"creator_user_id": sample_user['id']},
            json=clan_data
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == clan_data["name"]
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_create_clan_duplicate_name(self, client: AsyncClient, sample_user, sample_clan):
        """Ошибка при создании клана с дублирующимся именем"""
        clan_data = generate_clan_data()
        clan_data["name"] = sample_clan["name"]
        
        response = await client.post(
            "/clans/",
            params={"creator_user_id": sample_user['id']},
            json=clan_data
        )
        assert response.status_code == 400
        assert "уже существует" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_clan_creator_becomes_leader(self, client: AsyncClient, sample_user):
        """Создатель клана автоматически становится лидером"""
        clan_data = generate_clan_data()
        response = await client.post(
            "/clans/",
            params={"creator_user_id": sample_user['id']},
            json=clan_data
        )
        assert response.status_code == 201
        clan_id = response.json()["id"]
        
        # Проверить членов клана
        members_response = await client.get(f"/clans/{clan_id}/members")
        assert members_response.status_code == 200
        members = members_response.json()
        assert len(members) == 1
        assert members[0]["user_id"] == sample_user["id"]
        assert members[0]["role"] == "leader"
    
    @pytest.mark.asyncio
    async def test_add_clan_member(self, client: AsyncClient, sample_clan, test_db_session):
        """Добавление пользователя в клан"""
        # Создать второго пользователя
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        response = await client.post(
            f"/clans/{sample_clan['id']}/members/add",
            params={"user_id": user2.id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == user2.id
        assert data["clan_id"] == sample_clan["id"]
        assert data["role"] == "member"
    
    @pytest.mark.asyncio
    async def test_add_clan_member_with_role(self, client: AsyncClient, sample_clan, test_db_session):
        """Добавление пользователя в клан с определенной ролью"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        response = await client.post(
            f"/clans/{sample_clan['id']}/members/add",
            params={"user_id": user2.id, "role": "officer"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["role"] == "officer"
    
    @pytest.mark.asyncio
    async def test_add_clan_member_duplicate(self, client: AsyncClient, sample_clan, test_db_session):
        """Ошибка при добавлении пользователя, который уже в клане"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Добавить первый раз
        await client.post(
            f"/clans/{sample_clan['id']}/members/add",
            params={"user_id": user2.id}
        )
        
        # Попытка добавить второй раз
        response = await client.post(
            f"/clans/{sample_clan['id']}/members/add",
            params={"user_id": user2.id}
        )
        assert response.status_code == 400
        assert "уже в клане" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_clan_members(self, client: AsyncClient, sample_clan, test_db_session):
        """Получение списка членов клана"""
        # Добавить еще одного пользователя
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        await client.post(
            f"/clans/{sample_clan['id']}/members/add",
            params={"user_id": user2.id}
        )
        
        response = await client.get(f"/clans/{sample_clan['id']}/members")
        assert response.status_code == 200
        members = response.json()
        assert len(members) >= 2
    
    @pytest.mark.asyncio
    async def test_remove_clan_member(self, client: AsyncClient, sample_clan, test_db_session):
        """Удаление пользователя из клана"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Добавить
        await client.post(
            f"/clans/{sample_clan['id']}/members/add",
            params={"user_id": user2.id}
        )
        
        # Удалить
        response = await client.delete(f"/clans/{sample_clan['id']}/members/{user2.id}")
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    @pytest.mark.asyncio
    async def test_remove_clan_member_not_found(self, client: AsyncClient, sample_clan, test_db_session):
        """Ошибка при удалении пользователя, которого нет в клане"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        response = await client.delete(f"/clans/{sample_clan['id']}/members/{user2.id}")
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_list_clans(self, client: AsyncClient, sample_clan):
        """Получение списка всех кланов"""
        response = await client.get("/clans/")
        assert response.status_code == 200
        clans = response.json()
        assert isinstance(clans, list)
        assert len(clans) >= 1
    
    @pytest.mark.asyncio
    async def test_get_clan_by_id(self, client: AsyncClient, sample_clan):
        """Получение клана по ID"""
        response = await client.get(f"/clans/{sample_clan['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_clan["id"]
        assert data["name"] == sample_clan["name"]


class TestFriendshipFeatures:
    """Тесты для дружбы"""
    
    @pytest.mark.asyncio
    async def test_send_friend_request(self, client: AsyncClient, sample_user, test_db_session):
        """Отправка запроса на дружбу"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        response = await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_user["id"]
        assert data["friend_id"] == user2.id
        assert data["status"] == "pending"
    
    @pytest.mark.asyncio
    async def test_send_friend_request_to_self(self, client: AsyncClient, sample_user):
        """Ошибка при попытке добавить себя в друзья"""
        response = await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": sample_user['id']}
        )
        assert response.status_code == 400
        assert "себя" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_send_duplicate_friend_request(self, client: AsyncClient, sample_user, test_db_session):
        """Ошибка при дублировании запроса на дружбу"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Первый запрос
        await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        
        # Второй запрос (должен вернуть ошибку)
        response = await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        assert response.status_code == 400
    
    @pytest.mark.asyncio
    async def test_accept_friend_request(self, client: AsyncClient, sample_user, test_db_session):
        """Принятие запроса на дружбу"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Отправить запрос
        request_response = await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        friendship_id = request_response.json()["id"]
        
        # Принять запрос
        response = await client.post(f"/friendships/{friendship_id}/accept")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "accepted"
        assert data["accepted_at"] is not None
    
    @pytest.mark.asyncio
    async def test_delete_friendship(self, client: AsyncClient, sample_user, test_db_session):
        """Удаление дружбы"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Создать запрос
        request_response = await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        friendship_id = request_response.json()["id"]
        
        # Удалить
        response = await client.delete(f"/friendships/{friendship_id}")
        assert response.status_code == 200
        assert response.json()["success"] is True
    
    @pytest.mark.asyncio
    async def test_get_user_friends(self, client: AsyncClient, sample_user, test_db_session):
        """Получение списка друзей пользователя"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Создать и принять запрос
        request_response = await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        friendship_id = request_response.json()["id"]
        await client.post(f"/friendships/{friendship_id}/accept")
        
        # Получить друзей
        response = await client.get(f"/friendships/users/{sample_user['id']}")
        assert response.status_code == 200
        friendships = response.json()
        assert len(friendships) >= 1
    
    @pytest.mark.asyncio
    async def test_get_user_friends_filtered_by_status(self, client: AsyncClient, sample_user, test_db_session):
        """Получение друзей с фильтрацией по статусу"""
        user2_data = generate_user_data()
        user2 = User(**user2_data)
        test_db_session.add(user2)
        await test_db_session.commit()
        await test_db_session.refresh(user2)
        
        # Создать запрос (pending)
        await client.post(
            "/friendships/request",
            params={"user_id": sample_user['id'], "friend_id": user2.id}
        )
        
        # Получить только принятые запросы
        response = await client.get(
            f"/friendships/users/{sample_user['id']}",
            params={"status": "accepted"}
        )
        assert response.status_code == 200
        friendships = response.json()
        # Должен быть пустым, так как запрос еще не принят
        accepted = [f for f in friendships if f["status"] == "accepted"]
        assert len(accepted) == 0
