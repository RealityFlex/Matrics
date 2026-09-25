"""
Проверка подписи initData мини-приложения MAX.

Алгоритм (https://dev.max.ru/docs/webapps/validation):
    secret_key = HMAC_SHA256(key="WebAppData", msg=BOT_TOKEN)
    data_check_string = "\\n".join(sorted(f"{k}={v}" for k, v in params if k != "hash"))
    hash == hex(HMAC_SHA256(key=secret_key, msg=data_check_string))
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional
from urllib.parse import parse_qsl


class InitDataError(ValueError):
    """initData отсутствует, подделан или устарел"""


def max_email(max_user_id: int | str) -> str:
    """Служебный email пользователя MAX (исторический формат маппинга в проекте)"""
    return f"max_{max_user_id}@max.local"


def _secret_key(bot_token: str) -> bytes:
    return hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()


def sign_init_data(fields: Dict[str, Any], bot_token: str) -> str:
    """
    Подписать набор полей (используется в тестах и для локальной отладки).
    Возвращает строку initData в формате query string.
    """
    from urllib.parse import urlencode

    prepared = {k: (json.dumps(v, ensure_ascii=False, separators=(",", ":")) if isinstance(v, (dict, list)) else str(v))
                for k, v in fields.items()}
    check_string = "\n".join(f"{k}={prepared[k]}" for k in sorted(prepared))
    prepared["hash"] = hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(prepared)


def validate_init_data(
    init_data: Optional[str],
    bot_token: Optional[str],
    max_age_seconds: int = 86400,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Проверить initData и вернуть разобранные поля (`user` уже декодирован из JSON).
    Бросает InitDataError при любой проблеме.
    """
    if not init_data:
        raise InitDataError("initData отсутствует")
    if not bot_token:
        raise InitDataError("MAX_BOT_TOKEN не задан — проверка подписи невозможна")

    raw = init_data[1:] if init_data.startswith("#") else init_data
    pairs = parse_qsl(raw, keep_blank_values=True)
    data = dict(pairs)
    received_hash = data.pop("hash", None)
    if not received_hash:
        raise InitDataError("В initData нет подписи")

    check_string = "\n".join(f"{k}={data[k]}" for k in sorted(data))
    expected = hmac.new(_secret_key(bot_token), check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash.lower()):
        raise InitDataError("Подпись initData неверна")

    auth_date_raw = data.get("auth_date")
    if auth_date_raw:
        try:
            auth_date = int(auth_date_raw)
        except ValueError as exc:
            raise InitDataError("auth_date некорректен") from exc
        if auth_date > 10**11:  # на случай миллисекунд
            auth_date //= 1000
        current = now if now is not None else time.time()
        if max_age_seconds and current - auth_date > max_age_seconds:
            raise InitDataError("initData устарел")

    result: Dict[str, Any] = dict(data)
    if "user" in data:
        try:
            result["user"] = json.loads(data["user"])
        except json.JSONDecodeError as exc:
            raise InitDataError("Поле user не является JSON") from exc
    return result


def extract_max_user_id(fields: Dict[str, Any]) -> Optional[int]:
    user = fields.get("user") or {}
    user_id = user.get("id") or user.get("user_id")
    try:
        return int(user_id) if user_id is not None else None
    except (TypeError, ValueError):
        return None
