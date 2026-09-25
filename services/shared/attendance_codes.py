"""
Ротируемые коды отметки на занятии (TOTP-подобная схема).

Код не хранится в БД, а вычисляется из секрета занятия и номера временного окна:
    code = HMAC_SHA256(secret, f"{lesson_id}:{window}") -> 4 цифры
Поэтому GET-запрос кода ничего не пишет в БД, все экраны преподавателя показывают
один и тот же код, а при проверке принимаются текущее и предыдущее окно
(студент успевает ввести код, увиденный за секунду до смены).

Этот же код зашивается в QR-диплинк на мини-приложение MAX:
    https://max.ru/<bot>?startapp=att-<lesson_id>-<code>
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

CHECKIN_PAYLOAD_PREFIX = "att"
_PAYLOAD_RE = re.compile(r"att-(\d{1,10})-(\d{4})")


def window_seconds() -> int:
    """Длина окна ротации кода (сек). Читается на каждый вызов, чтобы тесты могли менять env."""
    try:
        value = int(os.getenv("LESSON_CODE_WINDOW_SECONDS", "30"))
    except ValueError:
        value = 30
    return max(5, value)


def _now(now: Optional[datetime] = None) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    if now.tzinfo is None:
        return now.replace(tzinfo=timezone.utc)
    return now


def new_secret() -> str:
    """Секрет для нового занятия"""
    return secrets.token_hex(16)


def current_window(now: Optional[datetime] = None) -> int:
    return int(_now(now).timestamp()) // window_seconds()


def seconds_until_rotation(now: Optional[datetime] = None) -> int:
    ts = int(_now(now).timestamp())
    size = window_seconds()
    return size - (ts % size)


def lesson_code(secret: str, lesson_id: int, window: int) -> str:
    digest = hmac.new(secret.encode(), f"{lesson_id}:{window}".encode(), hashlib.sha256).hexdigest()
    return f"{int(digest[:8], 16) % 10000:04d}"


def current_lesson_code(secret: str, lesson_id: int, now: Optional[datetime] = None) -> str:
    return lesson_code(secret, lesson_id, current_window(now))


def verify_lesson_code(
    secret: Optional[str],
    lesson_id: int,
    code: Optional[str],
    now: Optional[datetime] = None,
    accept_previous_windows: int = 1,
) -> bool:
    """Проверить код: принимается текущее окно и `accept_previous_windows` предыдущих."""
    if not secret or not code:
        return False
    code = code.strip()
    if not re.fullmatch(r"\d{4}", code):
        return False
    window = current_window(now)
    for offset in range(accept_previous_windows + 1):
        if hmac.compare_digest(lesson_code(secret, lesson_id, window - offset), code):
            return True
    return False


def build_checkin_payload(lesson_id: int, code: str) -> str:
    """Полезная нагрузка диплинка (разрешённые символы MAX startapp: [A-Za-z0-9_-])"""
    return f"{CHECKIN_PAYLOAD_PREFIX}-{lesson_id}-{code}"


def parse_checkin_payload(value: Optional[str]) -> Optional[Tuple[int, str]]:
    """
    Разобрать payload отметки. Принимает как голую строку `att-12-0457`,
    так и полный URL (`https://max.ru/bot?startapp=att-12-0457`) — это результат
    сканирования QR через openCodeReader.
    """
    if not value:
        return None
    match = _PAYLOAD_RE.search(value)
    if not match:
        return None
    return int(match.group(1)), match.group(2)


def build_deep_links(bot_username: Optional[str], payload: str) -> Dict[str, Optional[str]]:
    """Диплинки на мини-приложение (startapp) и на чат с ботом (start)"""
    bot = (bot_username or "").lstrip("@").strip()
    if not bot:
        return {"startapp_url": None, "start_url": None}
    return {
        "startapp_url": f"https://max.ru/{bot}?startapp={payload}",
        "start_url": f"https://max.ru/{bot}?start={payload}",
    }
