"""
Бот в групповом чате учебной группы MAX.

* Бота добавили в чат (bot_added) → он объясняет, как привязать чат к группе.
* /bindgroup <код куратора> → чат получает напоминания о парах, сообщения о командной
  цели («группа отметилась на 80% — бонус всем») и итоги пар с лучшими сериями.
* /group → прогресс группы. Обычные сообщения участников бот в чате не комментирует.
"""
import logging
from typing import Any, Dict, Optional

import httpx

from services.max_bot_service.max_api_client import MaxApiClient
from services.max_bot_service.utils.keyboards import open_app_button
from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)

WELCOME = """👋 *Привет! Я бот «Матрикс».*

Я помогаю группе не пропускать пары: напоминаю о занятиях, считаю командную цель и подвожу итоги.

*Куратор, привяжите чат к группе:* отправьте сюда
`/bindgroup <код куратора>` — код есть в кабинете куратора в мини-приложении."""


def is_group_chat(update: Dict[str, Any]) -> bool:
    recipient = (update.get("message") or {}).get("recipient") or {}
    return recipient.get("chat_type") in ("chat", "channel")


def chat_id_of(update: Dict[str, Any]) -> Optional[int]:
    recipient = (update.get("message") or {}).get("recipient") or {}
    return recipient.get("chat_id") or update.get("chat_id")


def _detail(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            return exc.response.json().get("detail", str(exc))
        except Exception:
            return str(exc)
    text = str(exc)
    return text.split(": ", 1)[1] if text.startswith("HTTP ") and ": " in text else text


def _app_keyboard(text: str = "📱 Открыть Матрикс", start_param: str = "today") -> Optional[Dict[str, Any]]:
    button = open_app_button(text, start_param)
    if not button:
        return None
    return {"type": "inline_keyboard", "payload": {"buttons": [[button]]}}


class GroupChatHandler:
    def __init__(self, api_client: MaxApiClient):
        self.api_client = api_client

    async def _say(self, chat_id: int, text: str, keyboard: Optional[Dict[str, Any]] = None) -> None:
        await self.api_client.send_message(chat_id=chat_id, text=text,
                                           attachments=[keyboard] if keyboard else None, format="markdown")

    async def handle_bot_added(self, update: Dict[str, Any]) -> None:
        chat_id = update.get("chat_id")
        if chat_id:
            await self._say(chat_id, WELCOME)

    async def handle_command(self, update: Dict[str, Any], text: str) -> None:
        chat_id = chat_id_of(update)
        if not chat_id:
            return
        parts = text.split(maxsplit=1)
        command = parts[0].lower().split("@")[0]
        args = parts[1].strip() if len(parts) > 1 else ""

        if command == "/bindgroup":
            if not args:
                await self._say(chat_id, "Укажите код куратора: `/bindgroup ABCD123456`")
                return
            users = ServiceClient("user")
            try:
                result = await users.post("/users/internal/groups/bind-chat", json={"code": args, "chat_id": chat_id})
            except Exception as exc:
                await self._say(chat_id, f"❌ Не получилось привязать чат: {_detail(exc)}")
                return
            finally:
                await users.close()
            await self._say(
                chat_id,
                f"✅ Чат привязан к группе *{result['group_name']}*.\n\n"
                f"Я напомню о паре за 10 минут, а когда отметится {result['team_goal_percent']}% группы — "
                f"все отметившиеся получат командный бонус 🎁",
                _app_keyboard("📱 Открыть Матрикс"),
            )
        elif command in ("/group", "/start"):
            users = ServiceClient("user")
            try:
                info = await users.get(f"/users/internal/groups/by-chat/{chat_id}")
                text = (f"👥 *{info['group_name']}* — участников: {info['members']}\n"
                        f"Командная цель пары: {info['team_goal_percent']}% группы.\n\n"
                        f"Отметиться — в мини-приложении или в личке бота: `/checkin 1234`")
            except Exception:
                text = WELCOME
            finally:
                await users.close()
            await self._say(chat_id, text, _app_keyboard("✅ Отметиться на паре", "checkin"))
        elif command == "/help":
            await self._say(chat_id, WELCOME)
        # Остальные команды в групповом чате игнорируем, чтобы не засорять чат
