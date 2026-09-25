"""
Утилиты для отправки событий в сервис реального времени.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


async def push_parameters_update(
    user_id: int,
    *,
    coins: Optional[int] = None,
    satisfaction: Optional[int] = None,
    intelligence_level: Optional[int] = None,
    intelligence_points: Optional[int] = None,
    rating: Optional[float] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Отправить обновление параметров пользователя в realtime-сервис.
    Если, кроме user_id, не передано ни одного значения, событие не отправляется.
    """
    payload: Dict[str, Any] = {"user_id": user_id, "event": "parameters.updated"}

    if coins is not None:
        payload["coins"] = coins
    if satisfaction is not None:
        payload["satisfaction"] = satisfaction
    if intelligence_level is not None:
        payload["intelligence_level"] = intelligence_level
    if intelligence_points is not None:
        payload["intelligence_points"] = intelligence_points
    if rating is not None:
        payload["rating"] = rating
    if source:
        payload["source"] = source
    if metadata:
        payload["metadata"] = metadata

    # Если нечего отправлять - завершаем без вызова сервиса
    if len(payload) <= 2 and "event" in payload and "user_id" in payload:
        return

    client = ServiceClient("notification")
    try:
        await client.post("/events/parameters", json=payload)
    except Exception as exc:
        logger.warning("Не удалось отправить событие обновления параметров: %s", exc)
    finally:
        await client.close()


async def push_user_event(
    user_id: int,
    event: str,
    *,
    payload: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Отправить произвольное событие пользователю в realtime-сервис.

    Используется для уведомлений, не связанных напрямую с параметрами персонажа.
    """
    if user_id <= 0 or not event:
        return

    data: Dict[str, Any] = {
        "user_id": user_id,
        "event": event,
        "payload": payload or {},
    }
    if metadata:
        data["metadata"] = metadata

    client = ServiceClient("notification")
    try:
        await client.post("/events/generic", json=data)
    except Exception as exc:
        logger.warning("Не удалось отправить событие %s: %s", event, exc)
    finally:
        await client.close()


