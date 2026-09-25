"""
Тесты сценария отметки в чат-боте (без сети: MAX API и сервисы замоканы).
"""
from unittest.mock import AsyncMock, patch

import pytest

from services.max_bot_service.handlers.attendance_handler import AttendanceHandler
from services.max_bot_service.services.notification_service import NotificationService
from services.max_bot_service.utils.keyboards import KeyboardBuilder
from services.test_utils import MockServiceClient


class FakeUserService:
    async def get_or_create_user(self, max_user_id, max_user_name=None):
        return {"id": 42, "email": f"max_{max_user_id}@max.local"}


@pytest.fixture
def api():
    client = AsyncMock()
    client.send_message = AsyncMock(return_value={})
    client.answer_callback = AsyncMock(return_value={})
    return client


@pytest.fixture
def handler(api):
    return AttendanceHandler(api, FakeUserService(), KeyboardBuilder())


class TestBotCheckIn:
    @pytest.mark.asyncio
    async def test_qr_payload_triggers_internal_check_in(self, handler, api):
        events = MockServiceClient("event")
        events.set_response("/internal/lessons/12/check-in", {"status": "checked_in"})
        with patch("services.max_bot_service.handlers.attendance_handler.ServiceClient", return_value=events):
            handled = await handler.handle_start_payload(1001, "att-12-0457")
        assert handled is True
        # Успех подтверждает event-service отдельным уведомлением — бот не дублирует
        api.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_unknown_payload_ignored(self, handler):
        assert await handler.handle_start_payload(1001, "promo-2026") is False

    @pytest.mark.asyncio
    async def test_error_is_explained_to_user(self, handler, api):
        events = MockServiceClient("event")
        events.post_mock.side_effect = Exception("HTTP 400: Неверный или устаревший код.")
        with patch("services.max_bot_service.handlers.attendance_handler.ServiceClient", return_value=events):
            await handler.check_in(1001, 12, "0000", "code")
        text = api.send_message.call_args.kwargs["text"]
        assert "Неверный или устаревший код" in text

    @pytest.mark.asyncio
    async def test_checkin_without_code_shows_help(self, handler, api):
        await handler.handle_checkin_command(1001, "")
        assert "Как отметиться" in api.send_message.call_args.kwargs["text"]


class TestAttendanceNotification:
    @pytest.mark.asyncio
    async def test_notification_text(self, api):
        service = NotificationService(api)
        with patch("services.max_bot_service.services.notification_service.get_max_user_id",
                   new=AsyncMock(return_value=1001)):
            ok = await service.send_attendance_confirmed_notification(
                user_id=42,
                lesson_name="Матанализ",
                rewards={"coins": 5, "intelligence_points": 15, "satisfaction": 8},
                character={"mood": "happy", "mood_label": "доволен", "satisfaction_before": 60, "satisfaction": 68},
                streak={"current": 3},
                unlocked_sets=[{"name": "Эрудит"}],
            )
        assert ok is True
        text = api.send_message.call_args.kwargs["text"]
        assert "Матанализ" in text and "+5" in text and "60 → 68" in text
        assert "Серия посещений: 3" in text and "Эрудит" in text


class TestGroupChat:
    @pytest.mark.asyncio
    async def test_bindgroup_and_ignore_chatter(self, api):
        from services.max_bot_service.handlers.group_handler import GroupChatHandler, is_group_chat

        handler = GroupChatHandler(api)
        update = {"message": {"recipient": {"chat_id": -77, "chat_type": "chat"}, "sender": {"user_id": 1}}}
        assert is_group_chat(update)
        users = MockServiceClient("user")
        users.set_response("/users/internal/groups/bind-chat", {"group_name": "ИС-11", "team_goal_percent": 80, "group_id": 1})
        with patch("services.max_bot_service.handlers.group_handler.ServiceClient", return_value=users):
            await handler.handle_command(update, "/bindgroup ABCDEF1234")
        assert api.send_message.call_args.kwargs["chat_id"] == -77
        assert "ИС-11" in api.send_message.call_args.kwargs["text"]

        api.send_message.reset_mock()
        await handler.handle_command(update, "/tasks")  # личные команды в чате группы игнорируются
        api.send_message.assert_not_called()

    @pytest.mark.asyncio
    async def test_join_payload(self, handler, api):
        users = MockServiceClient("user")
        users.set_response("/users/internal/join", {"kind": "student", "group": {"id": 1, "name": "ИС-11"},
                                                    "organization": {"short_name": "ККИ"}, "already": False})
        with patch("services.max_bot_service.handlers.attendance_handler.ServiceClient", return_value=users):
            assert await handler.handle_start_payload(1001, "join-ABCDEF12") is True
        assert "ИС-11" in api.send_message.call_args.kwargs["text"]
