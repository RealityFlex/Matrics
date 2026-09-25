"""
Зависимости FastAPI для минимальной авторизации.

* Администратор/куратор в веб-панели: заголовок `X-Admin-Token` == env ADMIN_TOKEN.
  Если ADMIN_TOKEN не задан — проверка отключена (локальная разработка, тесты),
  в лог пишется предупреждение.
* Студент в мини-приложении MAX: заголовок `X-Max-Init-Data` с подписанным initData.
  В режиме AUTH_MODE=lenient допускается старый способ `?user_id=` (веб-демо вне MAX).
"""
from __future__ import annotations

import hmac
import logging
import os
from dataclasses import dataclass
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.database import get_db
from services.shared.max_auth import InitDataError, extract_max_user_id, max_email, validate_init_data
from services.shared.models.user import User

logger = logging.getLogger(__name__)
_warned_no_admin_token = False

ROLE_STUDENT = "student"
ROLE_CURATOR = "curator"
ROLE_ADMIN = "admin"
STAFF_ROLES = {ROLE_CURATOR, ROLE_ADMIN}


def _env_flag(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def auth_mode() -> str:
    return os.getenv("AUTH_MODE", "lenient").strip().lower()


def admin_token_configured() -> bool:
    return bool(os.getenv("ADMIN_TOKEN", "").strip())


def is_valid_admin_token(token: Optional[str]) -> bool:
    expected = os.getenv("ADMIN_TOKEN", "").strip()
    if not expected or not token:
        return False
    return hmac.compare_digest(expected, token.strip())


def _warn_no_admin_token() -> None:
    global _warned_no_admin_token
    if not _warned_no_admin_token:
        logger.warning("ADMIN_TOKEN не задан: административные эндпоинты не защищены (допустимо только локально)")
        _warned_no_admin_token = True


async def require_admin(x_admin_token: Optional[str] = Header(None)) -> None:
    """Защита административных эндпоинтов"""
    if not admin_token_configured():
        _warn_no_admin_token()
        return
    if not is_valid_admin_token(x_admin_token):
        raise HTTPException(status_code=401, detail="Требуется токен администратора")


async def get_verified_max_user(request: Request, db: AsyncSession) -> Optional[User]:
    """Пользователь из подписанного initData MAX или None, если заголовка нет"""
    init_data = request.headers.get("X-Max-Init-Data")
    if not init_data:
        return None
    try:
        fields = validate_init_data(init_data, os.getenv("MAX_BOT_TOKEN"))
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail=f"Не удалось подтвердить вход через MAX: {exc}")
    max_user_id = extract_max_user_id(fields)
    if max_user_id is None:
        raise HTTPException(status_code=401, detail="В данных MAX нет пользователя")
    result = await db.execute(select(User).where(User.email == max_email(max_user_id)))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь MAX ещё не зарегистрирован — откройте мини-приложение заново")
    return user


async def resolve_acting_user_id(
    request: Request,
    as_user_id: Optional[int] = Query(None, alias="user_id", description="ID пользователя (только в режиме AUTH_MODE=lenient)"),
    db: AsyncSession = Depends(get_db),
) -> int:
    """Кто выполняет действие: пользователь из initData, иначе (lenient) — ?user_id="""
    user = await get_verified_max_user(request, db)
    if user is not None:
        if as_user_id is not None and as_user_id != user.id:
            raise HTTPException(status_code=403, detail="Нельзя выполнять действия от имени другого пользователя")
        return user.id
    if auth_mode() == "lenient" and as_user_id is not None:
        return as_user_id
    raise HTTPException(status_code=401, detail="Требуется вход через MAX")


async def require_verified_user(
    request: Request,
    as_user_id: Optional[int] = Query(None, alias="user_id", description="ID пользователя (если подпись MAX не обязательна)"),
    db: AsyncSession = Depends(get_db),
) -> int:
    """
    Для действий, которые начисляют награды (отметка, «заморозка», покупка):
    при CHECKIN_REQUIRE_MAX_AUTH=true требуется подписанный initData.
    """
    if _env_flag("CHECKIN_REQUIRE_MAX_AUTH"):
        user = await get_verified_max_user(request, db)
        if user is None:
            raise HTTPException(status_code=401, detail="Откройте мини-приложение в MAX, чтобы отметиться")
        if as_user_id is not None and as_user_id != user.id:
            raise HTTPException(status_code=403, detail="Нельзя выполнять действия от имени другого пользователя")
        return user.id
    return await resolve_acting_user_id(request, as_user_id, db)


@dataclass
class StaffContext:
    role: str
    user_id: Optional[int] = None
    group_ids: Optional[List[int]] = None  # None — доступ ко всем группам

    def can_view_group(self, group_id: int) -> bool:
        return self.group_ids is None or group_id in self.group_ids


async def require_staff(
    request: Request,
    x_admin_token: Optional[str] = Header(None),
    as_user_id: Optional[int] = Query(None, alias="user_id", include_in_schema=False),
    db: AsyncSession = Depends(get_db),
) -> StaffContext:
    """
    Куратор (через MAX, роль curator) или администратор (токен).
    В AUTH_MODE=lenient (веб-демо) куратор может передать ?user_id= — как и остальные запросы демо.
    """
    if is_valid_admin_token(x_admin_token):
        return StaffContext(role=ROLE_ADMIN)

    user = await get_verified_max_user(request, db)
    if user is None and as_user_id is not None and auth_mode() == "lenient":
        user = (await db.execute(select(User).where(User.id == as_user_id))).scalar_one_or_none()
    if user is not None and (user.role or ROLE_STUDENT) in STAFF_ROLES:
        if user.role == ROLE_ADMIN:
            return StaffContext(role=ROLE_ADMIN, user_id=user.id)
        from services.shared.models.social import group_curators

        rows = await db.execute(select(group_curators.c.group_id).where(group_curators.c.user_id == user.id))
        return StaffContext(role=ROLE_CURATOR, user_id=user.id, group_ids=[r[0] for r in rows.all()])

    if not admin_token_configured() and user is None:
        _warn_no_admin_token()
        return StaffContext(role=ROLE_ADMIN)

    if user is None and not x_admin_token:
        raise HTTPException(status_code=401, detail="Требуется вход куратора (MAX) или токен администратора")
    raise HTTPException(status_code=403, detail="Доступ только для куратора или администратора")
