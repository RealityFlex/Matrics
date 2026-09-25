"""
Unit тесты для Character Service
"""
import pytest
from httpx import AsyncClient

from services.test_utils import generate_character_data


class TestCharacterCRUD:
    """Тесты CRUD операций для персонажей"""
    
    @pytest.mark.asyncio
    async def test_create_character(self, client: AsyncClient, sample_user):
        """Успешное создание персонажа"""
        char_data = generate_character_data(sample_user["id"])
        
        response = await client.post("/characters/", json=char_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == sample_user["id"]
        assert data["name"] == char_data["name"]
        assert data["satisfaction"] == 50
        assert data["intelligence_level"] == 1
        assert data["intelligence_points"] == 0
        assert data["rating"] == (0 + 50 / 2 + 1 * 100)  # Формула рейтинга
    
    @pytest.mark.asyncio
    async def test_create_character_user_not_found(self, client: AsyncClient):
        """Ошибка: пользователь не существует"""
        char_data = generate_character_data(99999)
        
        response = await client.post("/characters/", json=char_data)
        
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_create_character_duplicate(self, client: AsyncClient, sample_character):
        """Ошибка: у пользователя уже есть персонаж"""
        char_data = generate_character_data(sample_character["user_id"])
        
        response = await client.post("/characters/", json=char_data)
        
        assert response.status_code == 400
        assert "уже есть персонаж" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_get_character_by_id(self, client: AsyncClient, sample_character):
        """Получение персонажа по ID"""
        response = await client.get(f"/characters/{sample_character['id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_character["id"]
        assert data["name"] == sample_character["name"]
    
    @pytest.mark.asyncio
    async def test_get_character_by_user_id(self, client: AsyncClient, sample_character):
        """Получение персонажа по user_id"""
        response = await client.get(f"/characters/user/{sample_character['user_id']}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["user_id"] == sample_character["user_id"]
    
    @pytest.mark.asyncio
    async def test_get_character_not_found(self, client: AsyncClient):
        """Персонаж не найден"""
        response = await client.get("/characters/99999")
        
        assert response.status_code == 404
    
    @pytest.mark.asyncio
    async def test_list_characters(self, client: AsyncClient, sample_character):
        """Список персонажей"""
        response = await client.get("/characters/")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1


class TestCharacterSatisfaction:
    """Тесты бизнес-логики удовлетворения"""
    
    @pytest.mark.asyncio
    async def test_adjust_satisfaction_increase(self, client: AsyncClient, sample_character):
        """Увеличение удовлетворения"""
        response = await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=20"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction"] == 70  # 50 + 20
    
    @pytest.mark.asyncio
    async def test_adjust_satisfaction_decrease(self, client: AsyncClient, sample_character):
        """Уменьшение удовлетворения"""
        response = await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=-30"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction"] == 20  # 50 - 30
    
    @pytest.mark.asyncio
    async def test_adjust_satisfaction_min_boundary(self, client: AsyncClient, sample_character):
        """Граница минимума (0)"""
        response = await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=-100"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction"] == 0  # Не может быть меньше 0
    
    @pytest.mark.asyncio
    async def test_adjust_satisfaction_max_boundary(self, client: AsyncClient, sample_character):
        """Граница максимума (100)"""
        response = await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=100"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction"] == 100  # Не может быть больше 100
    
    @pytest.mark.asyncio
    async def test_adjust_satisfaction_zero(self, client: AsyncClient, sample_character):
        """Изменение на 0"""
        initial_satisfaction = sample_character["satisfaction"]
        
        response = await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=0"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["satisfaction"] == initial_satisfaction


class TestCharacterIntelligence:
    """Тесты бизнес-логики интеллекта"""
    
    @pytest.mark.asyncio
    async def test_add_intelligence_points_no_level_up(self, client: AsyncClient, sample_character):
        """Добавление очков без повышения уровня"""
        response = await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 50}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["intelligence_level"] == 1  # Уровень не изменился
        assert data["intelligence_points"] == 50  # Очки накопились
        assert data["level_up"] is False
        assert data["levels_gained"] == 0
    
    @pytest.mark.asyncio
    async def test_add_intelligence_points_single_level_up(self, client: AsyncClient, sample_character):
        """Одно повышение уровня"""
        # Для level up с 1 до 2 нужно 100 очков (level * 100)
        response = await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 100}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["intelligence_level"] == 2
        assert data["intelligence_points"] == 0  # Очки потрачены
        assert data["level_up"] is True
        assert data["levels_gained"] == 1
    
    @pytest.mark.asyncio
    async def test_add_intelligence_points_multiple_level_up(self, client: AsyncClient, sample_character):
        """Несколько повышений уровня подряд"""
        # Level 1->2: 100 очков
        # Level 2->3: 200 очков
        # Level 3->4: 300 очков
        # Всего: 600 очков
        response = await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 600}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["intelligence_level"] == 4
        assert data["intelligence_points"] == 0
        assert data["level_up"] is True
        assert data["levels_gained"] == 3
    
    @pytest.mark.asyncio
    async def test_add_intelligence_points_with_remainder(self, client: AsyncClient, sample_character):
        """Повышение уровня с остатком очков"""
        # 150 очков: 100 для level up, 50 остается
        response = await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 150}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["intelligence_level"] == 2
        assert data["intelligence_points"] == 50
        assert data["level_up"] is True
    
    @pytest.mark.asyncio
    async def test_add_intelligence_points_progressive(self, client: AsyncClient, sample_character):
        """Прогрессивное повышение уровней"""
        # Первое добавление: 100 очков -> level 2
        response1 = await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 100}
        )
        assert response1.json()["intelligence_level"] == 2
        
        # Второе добавление: 200 очков -> level 3
        response2 = await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 200}
        )
        assert response2.json()["intelligence_level"] == 3


class TestCharacterBonusPoints:
    """Тесты бонусных очков"""
    
    @pytest.mark.asyncio
    async def test_add_bonus_points(self, client: AsyncClient, sample_character):
        """Добавление бонусных очков"""
        response = await client.post(
            f"/characters/{sample_character['id']}/bonus/add?points=50"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["bonus_points"] == 50
    
    @pytest.mark.asyncio
    async def test_add_bonus_points_multiple_times(self, client: AsyncClient, sample_character):
        """Множественное добавление бонусных очков"""
        await client.post(
            f"/characters/{sample_character['id']}/bonus/add?points=30"
        )
        
        response = await client.post(
            f"/characters/{sample_character['id']}/bonus/add?points=20"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["bonus_points"] == 50


class TestCharacterRating:
    """Тесты расчета рейтинга"""
    
    @pytest.mark.asyncio
    async def test_rating_calculation(self, client: AsyncClient, sample_character):
        """Проверка формулы рейтинга"""
        # Рейтинг = intelligence_points + (satisfaction / 2) + (intelligence_level * 100)
        # Начальные значения: satisfaction=50, level=1, intelligence_points=0
        # Рейтинг = 0 + (50 / 2) + (1 * 100) = 25 + 100 = 125
        
        response = await client.get(f"/characters/{sample_character['id']}/rating")
        
        assert response.status_code == 200
        data = response.json()
        expected_rating = 0 + (50 / 2) + (1 * 100)
        assert data["rating"] == expected_rating
    
    @pytest.mark.asyncio
    async def test_rating_after_satisfaction_change(self, client: AsyncClient, sample_character):
        """Рейтинг после изменения удовлетворения"""
        # Увеличить удовлетворение до 100
        await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=50"
        )
        
        response = await client.get(f"/characters/{sample_character['id']}/rating")
        
        assert response.status_code == 200
        data = response.json()
        # Рейтинг = 0 + (100 / 2) + (1 * 100) = 50 + 100 = 150
        assert data["rating"] == 150.0
    
    @pytest.mark.asyncio
    async def test_rating_after_level_up(self, client: AsyncClient, sample_character):
        """Рейтинг после повышения уровня"""
        # Повысить уровень до 2
        await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 100}
        )
        
        response = await client.get(f"/characters/{sample_character['id']}/rating")
        
        assert response.status_code == 200
        data = response.json()
        # Рейтинг = 0 + (50 / 2) + (2 * 100) = 25 + 200 = 225
        assert data["rating"] == 225.0
    
    @pytest.mark.asyncio
    async def test_rating_with_all_factors(self, client: AsyncClient, sample_character):
        """Рейтинг с учетом всех факторов"""
        # Изменить удовлетворение
        await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=30"
        )
        
        # Повысить уровень
        await client.post(
            f"/characters/{sample_character['id']}/intelligence/add",
            json={"points": 100}
        )
        
        # Добавить бонусы
        await client.post(
            f"/characters/{sample_character['id']}/bonus/add?points=50"
        )
        
        response = await client.get(f"/characters/{sample_character['id']}/rating")
        
        assert response.status_code == 200
        data = response.json()
        # Рейтинг = 0 + (80 / 2) + (2 * 100) = 40 + 200 = 240
        assert data["rating"] == 240.0


class TestCharacterEdgeCases:
    """Тесты граничных случаев"""
    
    @pytest.mark.asyncio
    async def test_create_character_custom_values(self, client: AsyncClient, sample_user):
        """Создание персонажа с кастомными значениями"""
        char_data = {
            "user_id": sample_user["id"],
            "name": "TestChar",
            "satisfaction": 75,
            "intelligence_level": 3,
            "intelligence_points": 50,
            "bonus_points": 100
        }
        
        response = await client.post("/characters/", json=char_data)
        
        assert response.status_code == 201
        data = response.json()
        assert data["satisfaction"] == 75
        assert data["intelligence_level"] == 3
        assert data["intelligence_points"] == 50
        assert data["bonus_points"] == 100
    
    @pytest.mark.asyncio
    async def test_get_rating_updates_dynamically(self, client: AsyncClient, sample_character):
        """Рейтинг обновляется динамически"""
        # Получить начальный рейтинг
        response1 = await client.get(f"/characters/{sample_character['id']}/rating")
        initial_rating = response1.json()["rating"]
        
        # Изменить параметры
        await client.post(
            f"/characters/{sample_character['id']}/satisfaction/adjust?amount=10"
        )
        
        # Получить обновленный рейтинг
        response2 = await client.get(f"/characters/{sample_character['id']}/rating")
        new_rating = response2.json()["rating"]
        
        # Рейтинг должен увеличиться на 10 / 2 = 5
        assert new_rating == initial_rating + 5

