"""
Отметка на занятии и серия посещений через чат-бота.

* `/checkin 1234` — отметиться на текущем занятии кодом с экрана преподавателя;
* QR-диплинк `https://max.ru/<бот>?start=att-<id>-<код>` — событие bot_started с payload
  (или текст `/start att-...`) → отметка без ввода кода;
* `/streak` — серия посещений и остаток «дней без штрафа»;
* кнопка «Взять день без штрафа» в уведомлении о пропуске.

Успешная отметка подтверждается уведомлением от event-service
(/notifications/attendance-confirmed), поэтому здесь отвечаем только на ошибки
и повторную отметку — без дублей сообщений.
"""
import logging
import re
from typing import Any, Dict, Optional

import httpx

from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.services.user_service import UserService
from services.max_bot_service.utils.keyboards import KeyboardBuilder
from services.shared.attendance_codes import parse_checkin_payload
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)

CHECKIN_HELP = """*✅ Как отметиться на паре*

1. Откройте мини-приложение и нажмите «Сканировать QR» — наведите камеру на QR-код с экрана преподавателя.
2. Или отправьте код с экрана командой: `/checkin 1234`

Код меняется каждые 30 секунд, поэтому отметиться можно только находясь на занятии."""


def _error_detail(exc: Exception) -> str:
    """Текст ошибки от сервиса: ServiceClient.post бросает Exception('HTTP 400: ...')"""
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json().get("detail") or str(exc)
        except Exception:
            return str(exc)
    match = re.match(r"HTTP \d+: (.*)", str(exc), re.S)
    return match.group(1) if match else "Сервис временно недоступен, попробуйте ещё раз"


class AttendanceHandler:
    def __init__(self, api_client: MaxApiClient, user_service: UserService, keyboard_builder: KeyboardBuilder):
        self.api_client = api_client
        self.user_service = user_service
        self.keyboard_builder = keyboard_builder

    async def _internal_user_id(self, max_user_id: int, max_user_name: Optional[str]) -> int:
        user = await self.user_service.get_or_create_user(max_user_id, max_user_name=max_user_name)
        return user.get("id") if isinstance(user, dict) else user.id

    async def _reply(self, max_user_id: int, text: str, keyboard: Optional[Dict[str, Any]] = None) -> None:
        await self.api_client.send_message(
            user_id=max_user_id, text=text, attachments=[keyboard] if keyboard else None, format="markdown"
        )

    async def send_help(self, max_user_id: int, callback_id: Optional[str] = None) -> None:
        keyboard = self.keyboard_builder.build_checkin_keyboard()
        if callback_id:
            await self.api_client.answer_callback(
                callback_id=callback_id,
                message={"text": CHECKIN_HELP, "attachments": [keyboard], "format": "markdown"},
            )
        else:
            await self._reply(max_user_id, CHECKIN_HELP, keyboard)

    async def check_in(self, max_user_id: int, lesson_id: int, code: str, method: str,
                       max_user_name: Optional[str] = None) -> None:
        user_id = await self._internal_user_id(max_user_id, max_user_name)
        events = ServiceClient("event")
        try:
            result = await events.post(
                f"/internal/lessons/{lesson_id}/check-in",
                json={"user_id": user_id, "code": code, "method": method},
            )
        except Exception as exc:
            await self._reply(max_user_id, f"❌ Не получилось отметиться: {_error_detail(exc)}",
                              self.keyboard_builder.build_checkin_keyboard())
            return
        finally:
            await events.close()

        if isinstance(result, dict) and result.get("status") == "already":
            lesson = (result.get("lesson") or {}).get("name", "занятии")
            await self._reply(max_user_id, f"👌 Вы уже отмечены на «{lesson}».",
                              self.keyboard_builder.build_attendance_keyboard())
        # checked_in: уведомление с наградами придёт от event-service

    async def handle_checkin_command(self, max_user_id: int, args: str, max_user_name: Optional[str] = None) -> None:
        code = (args or "").strip()
        payload = parse_checkin_payload(code)
        if payload:
            await self.check_in(max_user_id, payload[0], payload[1], "qr", max_user_name)
            return
        if not re.fullmatch(r"\d{4}", code):
            await self.send_help(max_user_id)
            return

        user_id = await self._internal_user_id(max_user_id, max_user_name)
        events = ServiceClient("event")
        try:
            lesson = await events.get(f"/schedule/users/{user_id}/current-lesson")
        except Exception as exc:
            text = "Сейчас у вас нет занятия, на котором можно отметиться." \
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 404 \
                else f"❌ {_error_detail(exc)}"
            await self._reply(max_user_id, text, self.keyboard_builder.build_checkin_keyboard())
            return
        finally:
            await events.close()
        await self.check_in(max_user_id, int(lesson["id"]), code, "code", max_user_name)

    async def handle_join(self, max_user_id: int, code: str, max_user_name: Optional[str] = None) -> None:
        """Вступление в группу (или роль куратора) по ссылке-приглашению"""
        user_id = await self._internal_user_id(max_user_id, max_user_name)
        users = ServiceClient("user")
        try:
            result = await users.post("/users/internal/join", json={"user_id": user_id, "code": code})
        except Exception as exc:
            await self._reply(max_user_id, f"❌ Не получилось вступить: {_error_detail(exc)}")
            return
        finally:
            await users.close()
        group = result["group"]["name"]
        org = (result.get("organization") or {}).get("short_name")
        where = f"*{group}*" + (f" ({org})" if org else "")
        if result["kind"] == "curator":
            text = (f"🎓 Вы куратор группы {where}.\n\nВ мини-приложении появился раздел «Мои группы»: "
                    f"QR для отметки на паре, посещаемость и студенты, которым нужна поддержка.")
            keyboard = self.keyboard_builder.build_curator_keyboard()
        else:
            text = (f"🎉 Вы в группе {where}!\n\nНа каждой паре отмечайтесь по QR с экрана преподавателя — "
                    f"персонаж будет расти, а группа — получать командные бонусы.")
            keyboard = self.keyboard_builder.build_attendance_keyboard()
        await self._reply(max_user_id, text, keyboard)

    async def handle_help_request(self, max_user_id: int, callback_id: str, max_user_name: Optional[str] = None) -> None:
        """Кнопка «Написать куратору»: обращение уходит куратору группы"""
        user_id = await self._internal_user_id(max_user_id, max_user_name)
        events = ServiceClient("event")
        try:
            result = await events.post("/internal/support/request", json={"user_id": user_id, "source": "bot"})
            if result.get("curators_notified"):
                text = "Куратор получил сообщение и свяжется с тобой. Ты не один 🤝"
            else:
                text = "Куратор группы пока не назначен. Обратись в деканат или к психологу вуза."
        except Exception as exc:
            text = f"❌ {_error_detail(exc)}"
        finally:
            await events.close()
        await self.api_client.answer_callback(callback_id=callback_id, notification=text)

    async def handle_start_payload(self, max_user_id: int, payload: Optional[str],
                                   max_user_name: Optional[str] = None) -> bool:
        """Обработать payload диплинка. True — payload распознан и обработан."""
        if payload and re.match(r"^(join|cur)-[A-Za-z0-9]{6,16}$", payload.strip()):
            await self.handle_join(max_user_id, payload.strip(), max_user_name)
            return True
        parsed = parse_checkin_payload(payload)
        if not parsed:
            return False
        await self.check_in(max_user_id, parsed[0], parsed[1], "qr", max_user_name)
        return True

    async def handle_streak(self, max_user_id: int, callback_id: Optional[str] = None,
                            max_user_name: Optional[str] = None) -> None:
        user_id = await self._internal_user_id(max_user_id, max_user_name)
        events = ServiceClient("event")
        try:
            streak = await events.get(f"/streaks/users/{user_id}")
        except Exception as exc:
            streak = None
            logger.warning("Не удалось получить серию: %s", exc)
        finally:
            await events.close()

        if not streak:
            text = "Не удалось получить серию посещений. Попробуйте позже."
        else:
            text = (
                f"*🔥 Серия посещений: {streak.get('current', 0)}*\n\n"
                f"Лучшая серия: {streak.get('best', 0)}\n"
                f"Посещено занятий: {streak.get('lessons_attended', 0)}\n"
                f"🧊 Дней без штрафа осталось: {streak.get('freezes_available', 0)} из {streak.get('freezes_limit', 0)} (на 30 дней)"
            )
            pending = streak.get("pending_misses") or []
            if pending:
                text += "\n\n*Пропуски, ожидающие решения:*\n" + "\n".join(f"• {m['lesson_name']}" for m in pending[:5])
        keyboard = self.keyboard_builder.build_attendance_keyboard()
        if callback_id:
            await self.api_client.answer_callback(
                callback_id=callback_id, message={"text": text, "attachments": [keyboard], "format": "markdown"}
            )
        else:
            await self._reply(max_user_id, text, keyboard)

    async def handle_freeze(self, max_user_id: int, miss_id: int, callback_id: str,
                            max_user_name: Optional[str] = None) -> None:
        user_id = await self._internal_user_id(max_user_id, max_user_name)
        events = ServiceClient("event")
        try:
            result = await events.post(f"/internal/streaks/misses/{miss_id}/freeze", json={"user_id": user_id})
            streak = (result or {}).get("streak") or {}
            text = (f"🧊 Готово! Пропуск не повлияет на персонажа и серию.\n"
                    f"Осталось «дней без штрафа»: {streak.get('freezes_available', 0)}")
        except Exception as exc:
            text = f"❌ {_error_detail(exc)}"
        finally:
            await events.close()
        await self.api_client.answer_callback(callback_id=callback_id, notification=text)
