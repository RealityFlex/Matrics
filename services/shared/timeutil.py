"""
Работа со временем: все даты в БД — UTC; расписание вводится в локальном времени
организации (APP_UTC_OFFSET_HOURS, по умолчанию Москва, UTC+3).
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def app_timezone() -> timezone:
    try:
        hours = float(os.getenv("APP_UTC_OFFSET_HOURS", "3"))
    except ValueError:
        hours = 3.0
    return timezone(timedelta(hours=hours))


def as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Привести datetime к aware UTC. Наивные значения из БД (SQLite) считаются UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def local_to_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Наивное время из формы/CSV считается локальным временем организации."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=app_timezone())
    return value.astimezone(timezone.utc)
