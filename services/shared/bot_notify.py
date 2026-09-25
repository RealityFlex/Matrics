"""
Отправка уведомлений через max-bot-service. Никогда не бросает исключений:
уведомление — побочный эффект, основной сценарий не должен от него зависеть.
Вызывать только при закрытой транзакции БД (HTTP-вызов может длиться секунды).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from services.shared.utils import ServiceClient

logger = logging.getLogger(__name__)


async def notify_bot(endpoint: str, payload: Dict[str, Any]) -> bool:
    bot = ServiceClient("max_bot")
    try:
        result = await bot.post(endpoint, json=payload)
        return bool(result.get("success", True)) if isinstance(result, dict) else True
    except Exception as exc:
        logger.warning("Уведомление %s не отправлено: %s", endpoint, exc)
        return False
    finally:
        await bot.close()


async def grant_reward(payload: Dict[str, Any]) -> Dict[str, Any] | None:
    reward = ServiceClient("reward")
    try:
        return await reward.post("/rewards/grant", json=payload)
    except Exception as exc:
        logger.warning("Награда не выдана (%s): %s", payload.get("source"), exc)
        return None
    finally:
        await reward.close()
