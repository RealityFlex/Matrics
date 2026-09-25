"""
Unit тесты для Competition Service - Соревнования
"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta
from services.test_utils import generate_competition_data, generate_user_data
from services.shared.models.user import User
from services.shared.models.competition import Competition
from sqlalchemy import select


class TestCompetitionCRUD:
    """Тесты CRUD для соревнований"""
    
    @pytest.mark.asyncio
    async def test_create_competition(self, client: AsyncClient):
        """Создание соревнования"""
        competition_data = generate_competition_data()
        response = await client.post("/competitions/", json=competition_data)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == competition_data["name"]
        assert data["is_active"] is True
        assert data["is_finished"] is False
    
    @pytest.mark.asyncio
    async def test_create_competition_invalid_time_range(self, client: AsyncClient):
        """Ошибка при создании соревнования с неправильным временем"""
        competition_data = generate_competition_data()
        competition_data["end_time"] = competition_data["start_time"]
        
        response = await client.post("/competitions/", json=competition_data)
        assert response.status_code == 400
        assert "позже времени начала" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_list_competitions(self, client: AsyncClient, sample_competition):
        """Получение списка соревнований"""
        response = await client.get("/competitions/")
        assert response.status_code == 200
        competitions = response.json()
        assert isinstance(competitions, list)
        assert len(competitions) >= 1
    
    @pytest.mark.asyncio
    async def test_list_competitions_active_only(self, client: AsyncClient):
        """Получение только активных соревнований"""
        # Создать активное соревнование
        active_data = generate_competition_data()
        active_data["is_active"] = True
        await client.post("/competitions/", json=active_data)
        
        # Создать неактивное соревнование
        inactive_data = generate_competition_data()
        inactive_data["is_active"] = False
        await client.post("/competitions/", json=inactive_data)
        
        response = await client.get("/competitions/?active_only=true")
        assert response.status_code == 200
        competitions = response.json()
        assert all(c["is_active"] and not c["is_finished"] for c in competitions)
    
    @pytest.mark.asyncio
    async def test_get_competition_by_id(self, client: AsyncClient, sample_competition):
        """Получение соревнования по ID"""
        response = await client.get(f"/competitions/{sample_competition['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_competition["id"]
        assert data["name"] == sample_competition["name"]
    
    @pytest.mark.asyncio
    async def test_update_competition(self, client: AsyncClient, sample_competition):
        """Обновление соревнования"""
        update_data = {"name": "Обновленное соревнование", "description": "Новое описание"}
        response = await client.put(f"/competitions/{sample_competition['id']}", json=update_data)
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Обновленное соревнование"
        assert data["description"] == "Новое описание"
    
    @pytest.mark.asyncio
    async def test_delete_competition(self, client: AsyncClient, sample_competition):
        """Удаление соревнования"""
        response = await client.delete(f"/competitions/{sample_competition['id']}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == sample_competition["id"]


class TestCompetitionParticipation:
    """Тесты для участия в соревнованиях"""
    
    @pytest.mark.asyncio
    async def test_join_competition(self, client: AsyncClient, sample_user, sample_competition):
        """Присоединение к соревнованию"""
        response = await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == sample_competition["id"]
        assert data["user_id"] == sample_user["id"]
        assert data["score"] == 0
        assert data["completed"] is False
        assert data["rank"] is None
    
    @pytest.mark.asyncio
    async def test_join_competition_duplicate(self, client: AsyncClient, sample_user, sample_competition):
        """Ошибка при повторном присоединении к соревнованию"""
        # Присоединиться первый раз
        await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        
        # Попытка присоединиться второй раз
        response = await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        assert response.status_code == 400
        assert "уже участвует" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_join_inactive_competition(self, client: AsyncClient, sample_user):
        """Ошибка при присоединении к неактивному соревнованию"""
        # Создать неактивное соревнование
        competition_data = generate_competition_data()
        competition_data["is_active"] = False
        response = await client.post("/competitions/", json=competition_data)
        competition_id = response.json()["id"]
        
        # Попытка присоединиться
        response = await client.post(
            f"/competitions/{competition_id}/join",
            params={"user_id": sample_user['id']}
        )
        assert response.status_code == 400
        assert "неактивно" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_join_finished_competition(self, client: AsyncClient, sample_user, test_db_session):
        """Ошибка при присоединении к завершенному соревнованию"""
        # Создать соревнование и завершить его
        competition_data = generate_competition_data()
        response = await client.post("/competitions/", json=competition_data)
        competition_id = response.json()["id"]
        
        # Завершить соревнование напрямую в БД
        from services.shared.models.competition import Competition
        result = await test_db_session.execute(
            select(Competition).where(Competition.id == competition_id)
        )
        competition = result.scalar_one_or_none()
        competition.is_finished = True
        await test_db_session.commit()
        
        # Попытка присоединиться
        response = await client.post(
            f"/competitions/{competition_id}/join",
            params={"user_id": sample_user['id']}
        )
        assert response.status_code == 400
        assert "завершено" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_update_participant_score(self, client: AsyncClient, sample_user, sample_competition):
        """Обновление счета участника"""
        # Присоединиться
        await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        
        # Обновить счет
        response = await client.post(
            f"/competitions/{sample_competition['id']}/participants/{sample_user['id']}/score",
            json={"score": 100}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["score"] == 100
    
    @pytest.mark.asyncio
    async def test_update_participant_score_not_participant(self, client: AsyncClient, sample_user, sample_competition):
        """Ошибка при обновлении счета несуществующего участника"""
        response = await client.post(
            f"/competitions/{sample_competition['id']}/participants/{sample_user['id']}/score",
            json={"score": 100}
        )
        assert response.status_code == 404
        assert "не найден" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_update_participant_score_negative(self, client: AsyncClient, sample_user, sample_competition):
        """Ошибка при отрицательном счете"""
        await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        
        response = await client.post(
            f"/competitions/{sample_competition['id']}/participants/{sample_user['id']}/score",
            json={"score": -10}
        )
        assert response.status_code == 422
    
    @pytest.mark.asyncio
    async def test_complete_competition(self, client: AsyncClient, sample_user, sample_competition):
        """Завершение соревнования для участника"""
        # Присоединиться и установить счет
        await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        await client.post(
            f"/competitions/{sample_competition['id']}/participants/{sample_user['id']}/score",
            json={"score": 100}
        )
        
        # Завершить
        response = await client.post(
            f"/competitions/{sample_competition['id']}/complete/{sample_user['id']}"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["completed"] is True
        assert data["completed_at"] is not None
    
    @pytest.mark.asyncio
    async def test_complete_competition_already_completed(self, client: AsyncClient, sample_user, sample_competition):
        """Ошибка при повторном завершении соревнования"""
        await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": sample_user['id']}
        )
        
        # Завершить первый раз
        await client.post(
            f"/competitions/{sample_competition['id']}/complete/{sample_user['id']}"
        )
        
        # Попытка завершить второй раз
        response = await client.post(
            f"/competitions/{sample_competition['id']}/complete/{sample_user['id']}"
        )
        assert response.status_code == 400
        assert "уже завершено" in response.json()["detail"]


class TestCompetitionRankings:
    """Тесты для рейтингов соревнований"""
    
    @pytest.mark.asyncio
    async def test_get_competition_leaderboard(self, client: AsyncClient, sample_competition, test_db_session):
        """Получение таблицы лидеров соревнования"""
        # Создать нескольких пользователей и добавить их в соревнование
        users = []
        for i in range(3):
            user_data = generate_user_data()
            user = User(**user_data)
            test_db_session.add(user)
            await test_db_session.commit()
            await test_db_session.refresh(user)
            users.append(user)
            
            # Присоединить к соревнованию
            await client.post(
                f"/competitions/{sample_competition['id']}/join",
                params={"user_id": user.id}
            )
            
            # Установить счет
            await client.post(
                f"/competitions/{sample_competition['id']}/participants/{user.id}/score",
                json={"score": (i + 1) * 100}  # 100, 200, 300
            )
        
        # Получить таблицу лидеров
        response = await client.get(f"/competitions/{sample_competition['id']}/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        assert isinstance(leaderboard, list)
        assert len(leaderboard) >= 3
        
        # Проверить сортировку (по убыванию счета)
        scores = [p["score"] for p in leaderboard]
        assert scores == sorted(scores, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_competition_leaderboard_empty(self, client: AsyncClient, sample_competition):
        """Получение таблицы лидеров пустого соревнования"""
        response = await client.get(f"/competitions/{sample_competition['id']}/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        assert isinstance(leaderboard, list)
        assert len(leaderboard) == 0
    
    @pytest.mark.asyncio
    async def test_get_competition_rankings_with_ranks(self, client: AsyncClient, sample_competition, test_db_session):
        """Получение рейтинга с автоматическим присвоением рангов"""
        # Создать участников с разными счетами
        users = []
        for i in range(3):
            user_data = generate_user_data()
            user = User(**user_data)
            test_db_session.add(user)
            await test_db_session.commit()
            await test_db_session.refresh(user)
            users.append(user)
            
            await client.post(
                f"/competitions/{sample_competition['id']}/join",
                params={"user_id": user.id}
            )
            
            await client.post(
                f"/competitions/{sample_competition['id']}/participants/{user.id}/score",
                json={"score": (3 - i) * 100}  # 300, 200, 100
            )
        
        # Получить таблицу лидеров (ранги присваиваются при finalize)
        response = await client.get(f"/competitions/{sample_competition['id']}/leaderboard")
        assert response.status_code == 200
        leaderboard = response.json()
        assert isinstance(leaderboard, list)
        assert len(leaderboard) >= 3
        
        # Проверить сортировку по счету
        scores = [p["score"] for p in leaderboard]
        assert scores == sorted(scores, reverse=True)


class TestCompetitionFinishing:
    """Тесты для завершения соревнований"""
    
    @pytest.mark.asyncio
    async def test_finish_competition(self, client: AsyncClient, sample_competition, test_db_session, mock_reward_service):
        """Завершение соревнования и выдача наград"""
        # Создать участников
        users = []
        for i in range(3):
            user_data = generate_user_data()
            user = User(**user_data)
            test_db_session.add(user)
            await test_db_session.commit()
            await test_db_session.refresh(user)
            users.append(user)
            
            await client.post(
                f"/competitions/{sample_competition['id']}/join",
                params={"user_id": user.id}
            )
            
            # Установить счета: 300, 200, 100
            await client.post(
                f"/competitions/{sample_competition['id']}/participants/{user.id}/score",
                json={"score": (3 - i) * 100}
            )
            
            # Завершить для каждого участника
            await client.post(
                f"/competitions/{sample_competition['id']}/complete/{user.id}"
            )
        
        # Завершить соревнование
        response = await client.post(f"/competitions/{sample_competition['id']}/finalize")
        assert response.status_code == 200
        data = response.json()
        assert data["competition_id"] == sample_competition["id"]
        assert data["total_participants"] == 3
        assert "rewards_distributed" in data
        
        # Проверить, что соревнование помечено как завершенное
        comp_response = await client.get(f"/competitions/{sample_competition['id']}")
        assert comp_response.status_code == 200
        comp_data = comp_response.json()
        assert comp_data["is_finished"] is True
    
    @pytest.mark.asyncio
    async def test_finish_competition_already_finished(self, client: AsyncClient, sample_competition, test_db_session, mock_reward_service):
        """Ошибка при повторном завершении соревнования"""
        # Создать участника для завершения
        user_data = generate_user_data()
        user = User(**user_data)
        test_db_session.add(user)
        await test_db_session.commit()
        await test_db_session.refresh(user)
        
        await client.post(
            f"/competitions/{sample_competition['id']}/join",
            params={"user_id": user.id}
        )
        
        # Завершить соревнование
        await client.post(f"/competitions/{sample_competition['id']}/finalize")
        
        # Попытка завершить второй раз
        response = await client.post(f"/competitions/{sample_competition['id']}/finalize")
        assert response.status_code == 400
        assert "уже завершено" in response.json()["detail"]
    
    @pytest.mark.asyncio
    async def test_finish_competition_without_participants(self, client: AsyncClient, sample_competition):
        """Ошибка при завершении соревнования без участников"""
        response = await client.post(f"/competitions/{sample_competition['id']}/finalize")
        assert response.status_code == 400
        assert "Нет участников" in response.json()["detail"]
