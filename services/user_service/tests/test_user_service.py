"""
Unit тесты для User Service
"""
import pytest
from httpx import AsyncClient

from services.test_utils import generate_user_data


class TestUserCRUD:
    """Тесты CRUD операций для пользователей"""
    
    @pytest.mark.asyncio
    async def test_create_user_success(self, client: AsyncClient):
        """Успешное создание пользователя"""
        user_data = generate_user_data()
        
        response = await client.post("/users/", json=user_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["username"] == user_data["username"]
        assert data["email"] == user_data["email"]
        assert data["coins"] == 0
        assert "id" in data
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, client: AsyncClient, sample_user):
        """Ошибка при дублировании email"""
        duplicate_data = generate_user_data()
        duplicate_data["email"] = sample_user["email"]
        
        response = await client.post("/users/", json=duplicate_data)
        
        assert response.status_code == 400
        assert "Email уже зарегистрирован" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_user_duplicate_username(self, client: AsyncClient, sample_user):
        """Ошибка при дублировании username"""
        duplicate_data = generate_user_data()
        duplicate_data["username"] = sample_user["username"]
        
        response = await client.post("/users/", json=duplicate_data)
        
        assert response.status_code == 400
        assert "Username уже занят" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_user_invalid_email(self, client: AsyncClient):
        """Валидация некорректного email"""
        user_data = generate_user_data()
        user_data["email"] = "invalid-email"
        
        response = await client.post("/users/", json=user_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_list_users(self, client: AsyncClient, sample_user):
        """Получение списка пользователей"""
        response = await client.get("/users/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        assert any(user["id"] == sample_user["id"] for user in data)
    
    @pytest.mark.asyncio
    async def test_list_users_pagination(self, client: AsyncClient):
        """Пагинация списка пользователей"""
        # Создать несколько пользователей
        for _ in range(5):
            await client.post("/users/", json=generate_user_data())
        
        # Тест с лимитом
        response = await client.get("/users/?limit=3")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        
        # Тест с offset
        response = await client.get("/users/?skip=2&limit=2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
    
    @pytest.mark.asyncio
    async def test_get_user_by_id(self, client: AsyncClient, sample_user):
        """Получение пользователя по ID"""
        response = await client.get(f"/users/{sample_user['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_user["id"]
        assert data["username"] == sample_user["username"]
        assert data["email"] == sample_user["email"]
    
    @pytest.mark.asyncio
    async def test_get_user_not_found(self, client: AsyncClient):
        """Пользователь не найден"""
        response = await client.get("/users/99999")
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_update_user(self, client: AsyncClient, sample_user):
        """Обновление пользователя"""
        update_data = {
            "username": "updated_username"
        }
        
        response = await client.put(f"/users/{sample_user['id']}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "updated_username"
        assert data["email"] == sample_user["email"]  # email не изменился
    
    @pytest.mark.asyncio
    async def test_update_user_email(self, client: AsyncClient, sample_user):
        """Обновление email пользователя"""
        update_data = {
            "email": "newemail@example.com"
        }
        
        response = await client.put(f"/users/{sample_user['id']}", json=update_data)
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "newemail@example.com"
    
    @pytest.mark.asyncio
    async def test_delete_user(self, client: AsyncClient, sample_user):
        """Удаление пользователя"""
        response = await client.delete(f"/users/{sample_user['id']}")
        
        assert response.status_code == 200
        
        # Проверить, что пользователь действительно удален
        get_response = await client.get(f"/users/{sample_user['id']}")
        assert get_response.status_code == 404


class TestUserCoins:
    """Тесты бизнес-логики монет"""
    
    @pytest.mark.asyncio
    async def test_get_user_coins(self, client: AsyncClient, sample_user):
        """Получение баланса монет пользователя"""
        response = await client.get(f"/users/{sample_user['id']}/coins")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_user["id"]
        assert data["coins"] == 0
    
    @pytest.mark.asyncio
    async def test_add_coins(self, client: AsyncClient, sample_user):
        """Добавление монет пользователю"""
        response = await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": 100}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_user["id"]
        assert data["coins"] == 100
        assert data["added"] == 100
    
    @pytest.mark.asyncio
    async def test_add_coins_multiple_times(self, client: AsyncClient, sample_user):
        """Множественное добавление монет"""
        # Первое добавление
        await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": 50}
        )
        
        # Второе добавление
        response = await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": 75}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["coins"] == 125
    
    @pytest.mark.asyncio
    async def test_subtract_coins(self, client: AsyncClient, sample_user):
        """Списание монет у пользователя"""
        # Сначала добавить монеты
        await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": 100}
        )
        
        # Списать монеты
        response = await client.post(
            f"/users/{sample_user['id']}/coins/subtract?amount=30"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["coins"] == 70
        assert data["subtracted"] == 30
    
    @pytest.mark.asyncio
    async def test_subtract_coins_insufficient(self, client: AsyncClient, sample_user):
        """Ошибка при недостаточном количестве монет"""
        # У пользователя 0 монет
        response = await client.post(
            f"/users/{sample_user['id']}/coins/subtract?amount=100"
        )
        
        assert response.status_code == 400
        assert "Недостаточно монет" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_subtract_coins_exact_amount(self, client: AsyncClient, sample_user):
        """Списание точного количества монет"""
        # Добавить 100 монет
        await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": 100}
        )
        
        # Списать все 100 монет
        response = await client.post(
            f"/users/{sample_user['id']}/coins/subtract?amount=100"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["coins"] == 0


class TestUserValidation:
    """Тесты валидации данных пользователя"""
    
    @pytest.mark.asyncio
    async def test_create_user_missing_username(self, client: AsyncClient):
        """Ошибка при отсутствии username"""
        user_data = generate_user_data()
        del user_data["username"]
        
        response = await client.post("/users/", json=user_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_user_missing_email(self, client: AsyncClient):
        """Ошибка при отсутствии email"""
        user_data = generate_user_data()
        del user_data["email"]
        
        response = await client.post("/users/", json=user_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_create_user_empty_username(self, client: AsyncClient):
        """Ошибка при пустом username"""
        user_data = generate_user_data()
        user_data["username"] = ""
        
        response = await client.post("/users/", json=user_data)
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_update_user_invalid_email(self, client: AsyncClient, sample_user):
        """Валидация некорректного email при обновлении"""
        update_data = {
            "email": "not-an-email"
        }
        
        response = await client.put(f"/users/{sample_user['id']}", json=update_data)
        
        assert response.status_code == 422


class TestUserEdgeCases:
    """Тесты граничных случаев"""
    
    @pytest.mark.asyncio
    async def test_get_user_with_zero_id(self, client: AsyncClient):
        """Пользователь с ID = 0"""
        response = await client.get("/users/0")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_get_user_with_negative_id(self, client: AsyncClient):
        """Пользователь с отрицательным ID"""
        response = await client.get("/users/-1")
        
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_add_zero_coins(self, client: AsyncClient, sample_user):
        """Добавление 0 монет"""
        response = await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": 0}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["coins"] == 0
    
    @pytest.mark.asyncio
    async def test_add_negative_coins(self, client: AsyncClient, sample_user):
        """Попытка добавить отрицательное количество монет"""
        response = await client.post(
            f"/users/{sample_user['id']}/coins/add",
            json={"amount": -100}
        )
        
        # Должна быть валидация
        assert response.status_code in [400, 422]

