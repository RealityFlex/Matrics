"""
Смоук группового чата бота без реального MAX: бота «добавляют» в чат, куратор привязывает
чат командой /bindgroup, участник пишет обычное сообщение (бот молчит), /group — статус.

    docker compose exec max-bot-service python /app/bot_group_smoke.py <chat_id> <код куратора>
"""
import asyncio
import json
import sys
import time

from services.max_bot_service.handlers.update_handler import UpdateHandler


class RecordingApi:
    def __init__(self):
        self.sent = []

    async def send_message(self, user_id=None, chat_id=None, text=None, attachments=None, **kwargs):
        buttons = [b["text"] for a in attachments or [] for row in a.get("payload", {}).get("buttons", []) for b in row]
        self.sent.append({"chat_id": chat_id, "user_id": user_id, "text": text, "buttons": buttons})
        return {}

    async def answer_callback(self, *args, **kwargs):
        return {}


async def main(chat_id: int, code: str):
    api = RecordingApi()
    handler = UpdateHandler(api)
    now = int(time.time() * 1000)
    member = {"user_id": 424242, "name": "Куратор"}

    def chat_message(text, mid):
        return {"update_type": "message_created", "timestamp": now,
                "message": {"sender": member, "recipient": {"chat_id": chat_id, "chat_type": "chat"},
                            "body": {"mid": mid, "text": text}}}

    steps = [
        ("бота добавили в чат", {"update_type": "bot_added", "chat_id": chat_id, "user": member, "timestamp": now}),
        ("/bindgroup", chat_message(f"/bindgroup {code}", "g1")),
        ("обычное сообщение в чате (бот молчит)", chat_message("Всем привет, кто идёт на пару?", "g2")),
        ("/group", chat_message("/group", "g3")),
    ]
    for title, update in steps:
        await handler.handle_update(update)
        print(f"\n=== {title}")
        print(json.dumps(api.sent, ensure_ascii=False, indent=1)[:700] if api.sent else "(нет сообщений)")
        api.sent.clear()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]), sys.argv[2]))
