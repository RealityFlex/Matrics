"""
Смоук-проверка чат-бота без реального MAX: обработчики бота работают с настоящими
сервисами внутри docker-сети, а вместо MAX API подставлена заглушка, которая
печатает, какие сообщения и кнопки бот отправил бы пользователю.

    docker compose exec max-bot-service python -m scripts.bot_smoke <max_user_id> <lesson_id> <code>
"""
import asyncio
import json
import sys
import time

from services.max_bot_service.handlers.update_handler import UpdateHandler
from services.max_bot_service.services.notification_service import NotificationService


class RecordingApi:
    def __init__(self):
        self.sent = []

    async def send_message(self, user_id=None, chat_id=None, text=None, attachments=None, **kwargs):
        buttons = []
        for attachment in attachments or []:
            for row in attachment.get("payload", {}).get("buttons", []):
                buttons.extend(f"{b['text']} [{b['type']}:{b.get('payload') or b.get('url')}]" for b in row)
        self.sent.append({"to": user_id, "text": text, "buttons": buttons})
        return {"message": {"body": {"mid": f"m{len(self.sent)}"}}}

    async def answer_callback(self, callback_id, message=None, notification=None):
        self.sent.append({"callback": callback_id, "text": (message or {}).get("text") or notification})
        return {}

    async def get_me(self):
        return {"name": "test"}


def show(title, api):
    print(f"\n=== {title}")
    for item in api.sent:
        print(json.dumps(item, ensure_ascii=False, indent=1)[:900])
    api.sent.clear()


async def main(max_user_id: int, lesson_id: int, code: str):
    api = RecordingApi()
    handler = UpdateHandler(api)
    now = int(time.time() * 1000)
    user = {"user_id": max_user_id, "name": "Бот-тест"}

    def message(text):
        return {"update_type": "message_created", "timestamp": now,
                "message": {"sender": user, "body": {"mid": f"x{time.time_ns()}", "text": text}}}

    await handler.handle_update({"update_type": "bot_started", "timestamp": now, "user": user, "payload": None})
    show("bot_started без payload → приветствие и меню", api)

    await handler.handle_update({"update_type": "bot_started", "timestamp": now + 1, "user": user,
                                 "payload": f"att-{lesson_id}-{code}"})
    show("bot_started с QR-payload → отметка (успех подтверждает event-service отдельным уведомлением)", api)

    await handler.handle_update(message(f"/checkin {code}"))
    show("/checkin <код> повторно → «уже отмечены»", api)

    await handler.handle_update(message("/checkin 12"))
    show("/checkin с некорректным кодом → подсказка", api)

    await handler.handle_update(message("/streak"))
    show("/streak", api)

    await handler.handle_update(message("/character"))
    show("/character", api)

    notifications = NotificationService(api)
    internal = await handler.command_handler.user_service.get_or_create_user(max_user_id)
    await notifications.send_attendance_confirmed_notification(
        user_id=internal["id"], lesson_name="Демо: Математический анализ",
        rewards={"coins": 5, "intelligence_points": 15, "satisfaction": 8},
        character={"mood": "happy", "mood_label": "доволен", "satisfaction_before": 60, "satisfaction": 68},
        streak={"current": 3}, unlocked_sets=[{"name": "Эрудит"}])
    show("уведомление об отметке (то, что шлёт event-service)", api)


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), int(sys.argv[2]), sys.argv[3]))
