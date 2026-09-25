"""
Вход через мини-приложение MAX и роли пользователей.

POST /users/auth/max — проверяет подпись initData (HMAC с токеном бота) и находит
или создаёт пользователя по MAX id. Заменяет прежнюю схему, где фронтенд скачивал
список всех пользователей и искал себя по email (ломалось после 100 пользователей).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import ROLE_ADMIN, ROLE_CURATOR, ROLE_STUDENT, require_admin
from services.shared.database import get_db
from services.shared.max_auth import InitDataError, extract_max_user_id, max_email, validate_init_data
from services.shared.models.social import StudentGroup, group_curators
from services.shared.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_ROLES = {ROLE_STUDENT, ROLE_CURATOR, ROLE_ADMIN}


class MaxAuthRequest(BaseModel):
    init_data: str


class RoleUpdateRequest(BaseModel):
    role: str
    group_ids: Optional[List[int]] = None


def _user_dict(user: User) -> Dict[str, Any]:
    return {"id": user.id, "username": user.username, "email": user.email, "coins": user.coins,
            "role": user.role or ROLE_STUDENT}


async def _unique_username(db: AsyncSession, base: str, max_id: int) -> str:
    base = (base or f"student{max_id}").strip()[:40] or f"student{max_id}"
    candidates = [base, f"{base}_{max_id}"[:50], f"max_{max_id}"]
    for name in candidates:
        if (await db.execute(select(User.id).where(User.username == name))).scalar_one_or_none() is None:
            return name
    return f"max_{max_id}_{os.urandom(2).hex()}"


@router.post("/users/auth/max")
async def auth_max(request: MaxAuthRequest, db: AsyncSession = Depends(get_db)):
    """Вход из мини-приложения MAX по подписанному initData"""
    try:
        fields = validate_init_data(request.init_data, os.getenv("MAX_BOT_TOKEN"))
    except InitDataError as exc:
        raise HTTPException(status_code=401, detail=f"Не удалось подтвердить вход через MAX: {exc}")
    max_id = extract_max_user_id(fields)
    if max_id is None:
        raise HTTPException(status_code=401, detail="В данных MAX нет пользователя")

    email = max_email(max_id)
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    is_new = False
    if user is None:
        # Ленивый импорт: create_user живёт в main.py (выдаёт стартовые предметы и персонажа)
        from services.user_service.main import UserCreate, create_user

        profile = fields.get("user") or {}
        base = profile.get("username") or profile.get("first_name") or f"student{max_id}"
        username = await _unique_username(db, base, max_id)
        try:
            user = await create_user(UserCreate(username=username, email=email), db)
            is_new = True
        except HTTPException as exc:
            # Параллельный вход того же пользователя: запись уже создана другим запросом
            await db.rollback()
            user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
            if user is None:
                raise exc

    return {
        "user": _user_dict(user),
        "is_new": is_new,
        "role": user.role or ROLE_STUDENT,
        "start_param": fields.get("start_param"),
    }


@router.get("/users/by-max/{max_user_id}")
async def get_user_by_max_id(max_user_id: int, db: AsyncSession = Depends(get_db)):
    """Пользователь по идентификатору MAX (используется ботом вместо перебора всех пользователей)"""
    user = (await db.execute(select(User).where(User.email == max_email(max_user_id)))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return _user_dict(user)


@router.get("/users/admin/verify", dependencies=[Depends(require_admin)])
async def verify_admin_token():
    """Проверка токена администратора (вход в админ-панель)"""
    return {"ok": True, "role": ROLE_ADMIN}


@router.put("/users/{user_id}/role", dependencies=[Depends(require_admin)])
async def set_user_role(user_id: int, request: RoleUpdateRequest, db: AsyncSession = Depends(get_db)):
    """Назначить роль (student / curator / admin) и группы куратора"""
    if request.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Роль должна быть одной из: {', '.join(sorted(VALID_ROLES))}")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    user.role = request.role
    if request.group_ids is not None:
        if request.group_ids:
            found = set((await db.execute(
                select(StudentGroup.id).where(StudentGroup.id.in_(request.group_ids))
            )).scalars().all())
            missing = set(request.group_ids) - found
            if missing:
                raise HTTPException(status_code=404, detail=f"Группы не найдены: {sorted(missing)}")
        await db.execute(delete(group_curators).where(group_curators.c.user_id == user_id))
        if request.group_ids:
            await db.execute(insert(group_curators).values(
                [{"group_id": gid, "user_id": user_id} for gid in sorted(set(request.group_ids))]
            ))
    await db.commit()
    groups = (await db.execute(select(group_curators.c.group_id).where(group_curators.c.user_id == user_id))).scalars().all()
    return {**_user_dict(user), "curator_group_ids": list(groups)}
