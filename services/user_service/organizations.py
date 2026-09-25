"""
Подключение образовательной организации «за 10 минут» и вступление по ссылке.

Администратор создаёт организацию: группы, расписание (тестовый CSV), брендированную
локацию персонажа. На выходе — ссылки-приглашения:
  * студентам:  https://max.ru/<бот>?startapp=join-<код группы>  (мини-приложение, вход автоматический)
  * кураторам:  https://max.ru/<бот>?startapp=cur-<код куратора>  (роль куратора + кабинет в MAX)
  * чат группы: добавить бота в чат и отправить /bindgroup <код куратора>
"""
from __future__ import annotations

import io
import logging
import os
import re
import secrets
import string
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, func, insert, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared.auth import ROLE_ADMIN, ROLE_CURATOR, StaffContext, require_admin, require_staff, require_verified_user
from services.shared.database import get_db
from services.shared.models.appearance import AppearanceKind, AppearanceSet, UnlockType
from services.shared.models.social import GroupMember, Organization, StudentGroup, group_curators
from services.shared.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter()

# Без похожих символов (O/0, I/1/L), чтобы код было легко продиктовать и набрать вручную
_ALPHABET = "".join(ch for ch in string.ascii_uppercase + string.digits if ch not in "O0I1L")
_CODE_RE = re.compile(r"(?:join|cur)-([A-Za-z0-9]{6,16})|^([A-Za-z0-9]{6,16})$", re.IGNORECASE)


def bot_username() -> str:
    return os.getenv("MAX_BOT_USERNAME", "").strip().lstrip("@")


def new_code(length: int = 8) -> str:
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))


def group_links(group: StudentGroup) -> Dict[str, Any]:
    bot = bot_username()
    base = f"https://max.ru/{bot}" if bot else None
    return {
        "invite_code": group.invite_code,
        "curator_code": group.curator_code,
        "student_link": f"{base}?startapp=join-{group.invite_code}" if base and group.invite_code else None,
        "student_bot_link": f"{base}?start=join-{group.invite_code}" if base and group.invite_code else None,
        "curator_link": f"{base}?startapp=cur-{group.curator_code}" if base and group.curator_code else None,
        "bind_chat_command": f"/bindgroup {group.curator_code}" if group.curator_code else None,
        "chat_bound": bool(group.max_chat_id),
    }


async def ensure_group_codes(db: AsyncSession, group: StudentGroup) -> StudentGroup:
    changed = False
    if not group.invite_code:
        group.invite_code = new_code()
        changed = True
    if not group.curator_code:
        group.curator_code = new_code(10)
        changed = True
    if changed:
        await db.commit()
        await db.refresh(group)
    return group


def parse_code(value: str) -> str:
    match = _CODE_RE.search((value or "").strip())
    if not match:
        raise HTTPException(status_code=400, detail="Неверный код приглашения")
    return (match.group(1) or match.group(2)).upper()


# ---------- Публичная конфигурация ----------

@router.get("/users/app-config")
async def app_config():
    """Ник бота и адрес мини-приложения — для кнопок «Поделиться» и ссылок во фронтенде"""
    bot = bot_username()
    return {
        "bot_username": bot or None,
        "bot_link": f"https://max.ru/{bot}" if bot else None,
        "webapp_url": os.getenv("WEBAPP_URL") or None,
    }


# ---------- Вступление по ссылке ----------

class JoinRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=40)


class InternalJoinRequest(JoinRequest):
    user_id: int


async def join_by_code(db: AsyncSession, user_id: int, raw_code: str) -> Dict[str, Any]:
    code = parse_code(raw_code)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    group = (await db.execute(select(StudentGroup).where(
        or_(StudentGroup.invite_code == code, StudentGroup.curator_code == code)
    ))).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Приглашение не найдено или устарело")
    organization = None
    if group.organization_id:
        org = (await db.execute(select(Organization).where(Organization.id == group.organization_id))).scalar_one_or_none()
        organization = {"id": org.id, "name": org.name, "short_name": org.short_name} if org else None

    if group.curator_code == code:
        if user.role != ROLE_ADMIN:
            user.role = ROLE_CURATOR
        exists = (await db.execute(select(group_curators.c.group_id).where(and_(
            group_curators.c.group_id == group.id, group_curators.c.user_id == user_id)))).first()
        if not exists:
            await db.execute(insert(group_curators).values(group_id=group.id, user_id=user_id))
        await db.commit()
        return {"kind": "curator", "group": {"id": group.id, "name": group.name}, "organization": organization,
                "already": bool(exists)}

    member = (await db.execute(select(GroupMember.id).where(and_(
        GroupMember.group_id == group.id, GroupMember.user_id == user_id)))).first()
    if not member:
        db.add(GroupMember(group_id=group.id, user_id=user_id))
        await db.commit()
    return {"kind": "student", "group": {"id": group.id, "name": group.name}, "organization": organization,
            "already": bool(member)}


@router.post("/users/join")
async def join(request: JoinRequest, user_id: int = Depends(require_verified_user), db: AsyncSession = Depends(get_db)):
    """Вступить в группу (или стать куратором) по коду из ссылки-приглашения"""
    return await join_by_code(db, user_id, request.code)


@router.post("/users/internal/join")
async def internal_join(request: InternalJoinRequest, db: AsyncSession = Depends(get_db)):
    """Вступление по ссылке через чат-бота (внутренний вызов, закрыт на gateway)"""
    return await join_by_code(db, request.user_id, request.code)


class BindChatRequest(BaseModel):
    code: str
    chat_id: int
    chat_title: Optional[str] = None


@router.post("/users/internal/groups/bind-chat")
async def bind_chat(request: BindChatRequest, db: AsyncSession = Depends(get_db)):
    """/bindgroup <код куратора> в групповом чате MAX: чат получает итоги пар и напоминания"""
    code = parse_code(request.code)
    group = (await db.execute(select(StudentGroup).where(StudentGroup.curator_code == code))).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Код куратора не найден. Возьмите его в кабинете куратора.")
    group.max_chat_id = request.chat_id
    await db.commit()
    return {"group_id": group.id, "group_name": group.name, "team_goal_percent": group.team_goal_percent}


@router.get("/users/internal/groups/by-chat/{chat_id}")
async def group_by_chat(chat_id: int, db: AsyncSession = Depends(get_db)):
    group = (await db.execute(select(StudentGroup).where(StudentGroup.max_chat_id == chat_id))).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Чат не привязан к группе")
    members = (await db.execute(select(func.count(GroupMember.id)).where(GroupMember.group_id == group.id))).scalar()
    return {"group_id": group.id, "group_name": group.name, "members": members, "team_goal_percent": group.team_goal_percent}


# ---------- Ссылки группы для куратора ----------

@router.get("/users/groups/{group_id}/invite")
async def group_invite(group_id: int, staff: StaffContext = Depends(require_staff), db: AsyncSession = Depends(get_db)):
    """Ссылки-приглашения группы (коды создаются при первом запросе)"""
    if not staff.can_view_group(group_id):
        raise HTTPException(status_code=403, detail="Нет доступа к этой группе")
    group = (await db.execute(select(StudentGroup).where(StudentGroup.id == group_id))).scalar_one_or_none()
    if group is None:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    group = await ensure_group_codes(db, group)
    return {"group_id": group.id, "group_name": group.name, **group_links(group)}


@router.get("/users/qr")
async def qr_png(data: str = Query(..., max_length=300), staff: StaffContext = Depends(require_staff)):
    """PNG с QR-кодом ссылки MAX (приглашения в группу) — для печати и показа на экране"""
    if not data.startswith("https://max.ru/"):
        raise HTTPException(status_code=400, detail="QR строится только для ссылок https://max.ru/")
    import qrcode

    qr = qrcode.QRCode(version=None, box_size=10, border=3)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


# ---------- Подключение организации ----------

class OnboardGroup(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    team_goal_percent: int = Field(80, ge=10, le=100)


class OnboardRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    short_name: Optional[str] = Field(None, max_length=50)
    city: Optional[str] = Field(None, max_length=100)
    brand_color: str = Field("#0B7A70", pattern=r"^#[0-9A-Fa-f]{6}$")
    groups: List[OnboardGroup] = Field(..., min_length=1, max_length=50)
    schedule_csv: Optional[str] = Field(None, description="CSV расписания (тестовая выгрузка); колонка group — имя группы")


async def _import_schedule(csv_text: str, created_by: int) -> Dict[str, Any]:
    headers = {"X-Admin-Token": os.getenv("ADMIN_TOKEN", "")}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post("http://event-service:8008/lessons/import", headers=headers,
                                     json={"created_by": created_by, "csv_text": csv_text, "is_simulated": True})
    if response.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Импорт расписания не выполнен: {response.text[:200]}")
    return response.json()


def _org_payload(org: Organization, groups: List[StudentGroup], members: Dict[int, int]) -> Dict[str, Any]:
    return {
        "id": org.id, "name": org.name, "short_name": org.short_name, "city": org.city, "brand_color": org.brand_color,
        "groups": [{"id": g.id, "name": g.name, "members": members.get(g.id, 0), "team_goal_percent": g.team_goal_percent,
                    **group_links(g)} for g in groups],
    }


@router.post("/users/organizations/onboard", dependencies=[Depends(require_admin)], status_code=201)
async def onboard_organization(request: OnboardRequest, db: AsyncSession = Depends(get_db)):
    """Подключить организацию: группы, ссылки-приглашения, брендированная локация, расписание"""
    if (await db.execute(select(Organization.id).where(Organization.name == request.name))).first():
        raise HTTPException(status_code=400, detail="Организация с таким названием уже подключена")
    names = [g.name for g in request.groups]
    taken = (await db.execute(select(StudentGroup.name).where(StudentGroup.name.in_(names)))).scalars().all()
    if taken:
        raise HTTPException(status_code=400, detail=f"Группы уже существуют: {', '.join(taken)}")

    short = request.short_name or request.name[:30]
    org = Organization(name=request.name, short_name=short, city=request.city,
                       brand_color=request.brand_color.upper(), theme_id=f"brand-{new_code(4).lower()}")
    db.add(org)
    await db.flush()
    # Технический владелец расписания организации (занятия ссылаются на создателя)
    system_user = User(username=f"org{org.id}_{new_code(4).lower()}", email=f"org{org.id}.system@matrix.local", role="admin")
    db.add(system_user)
    await db.flush()
    groups = []
    for item in request.groups:
        group = StudentGroup(name=item.name, description=f"{short}", creator_id=system_user.id, organization_id=org.id,
                             invite_code=new_code(), curator_code=new_code(10), team_goal_percent=item.team_goal_percent)
        db.add(group)
        groups.append(group)
    db.add(AppearanceSet(
        kind=AppearanceKind.ENVIRONMENT, code=f"brand_org{org.id}", name=f"Кампус {short}",
        description=f"Фирменная локация {short} — доступна студентам организации",
        asset_key="environment:brand", unlock_type=UnlockType.NONE, unlock_value=0,
        theme_id=org.brand_color, organization_id=org.id, sort_order=5,
    ))
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(status_code=400, detail=f"Не удалось создать организацию: {exc.orig}")

    schedule = None
    if request.schedule_csv:
        schedule = await _import_schedule(request.schedule_csv, system_user.id)
    for group in groups:
        await db.refresh(group)
    return {**_org_payload(org, groups, {}), "schedule": schedule}


@router.get("/users/organizations", dependencies=[Depends(require_admin)])
async def list_organizations(db: AsyncSession = Depends(get_db)):
    orgs = (await db.execute(select(Organization).order_by(Organization.id))).scalars().all()
    result = []
    for org in orgs:
        groups = (await db.execute(select(StudentGroup).where(StudentGroup.organization_id == org.id).order_by(StudentGroup.name))).scalars().all()
        counts = dict((await db.execute(
            select(GroupMember.group_id, func.count(GroupMember.id)).where(GroupMember.group_id.in_([g.id for g in groups] or [0]))
            .group_by(GroupMember.group_id)
        )).all())
        result.append(_org_payload(org, groups, counts))
    return result
