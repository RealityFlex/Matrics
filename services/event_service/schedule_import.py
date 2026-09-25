"""
Тестовая интеграция расписания: импорт занятий из CSV/JSON, имитирующего выгрузку
из внешней вузовской системы. Реальной интеграции нет — все импортированные занятия
помечаются source='test_import' и is_simulated=true и отображаются с бейджем
«Тестовые данные» (требование п.10 ограничений ТЗ).
"""
from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from services.shared import attendance_codes as codes
from services.shared.auth import require_admin
from services.shared.database import get_db
from services.shared.models.lesson import Lesson, lesson_groups
from services.shared.models.social import StudentGroup
from services.shared.models.user import User
from services.shared.timeutil import local_to_utc, utcnow

router = APIRouter()
TEST_SOURCE = "test_import"


class LessonImportRow(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(None, ge=5, le=600)
    location: Optional[str] = None
    group: Optional[str] = Field(None, description="Название или ID учебной группы")
    reward_coins: int = Field(5, ge=0)
    reward_intelligence: int = Field(10, ge=0)
    reward_satisfaction: int = Field(5, ge=0)


class LessonImportRequest(BaseModel):
    created_by: int
    lessons: Optional[List[LessonImportRow]] = None
    csv_text: Optional[str] = Field(None, description="CSV с заголовком: name,start_time,end_time|duration_minutes,location,group,...")
    default_group_ids: List[int] = []
    is_simulated: bool = True
    dry_run: bool = False


class DemoSeedRequest(BaseModel):
    group_id: int
    created_by: int


def _rows_from_csv(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text.strip()))
    rows = []
    for raw in reader:
        row = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in raw.items() if k}
        rows.append({k: v for k, v in row.items() if v not in ("", None)})
    return rows


async def _resolve_group(db: AsyncSession, ref: Optional[str], cache: Dict[str, Optional[int]]) -> Optional[int]:
    if not ref:
        return None
    if ref in cache:
        return cache[ref]
    query = select(StudentGroup.id).where(StudentGroup.id == int(ref)) if ref.isdigit() \
        else select(StudentGroup.id).where(StudentGroup.name == ref)
    group_id = (await db.execute(query)).scalar_one_or_none()
    cache[ref] = group_id
    return group_id


@router.post("/lessons/import", dependencies=[Depends(require_admin)])
async def import_lessons(request: LessonImportRequest, db: AsyncSession = Depends(get_db)):
    """Импорт тестового расписания (CSV-текст или JSON-список)"""
    if (await db.execute(select(User.id).where(User.id == request.created_by))).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Пользователь-создатель не найден")

    raw_rows: List[Dict[str, Any]] = []
    if request.csv_text:
        raw_rows.extend(_rows_from_csv(request.csv_text))
    if request.lessons:
        raw_rows.extend(row.model_dump(exclude_none=True) for row in request.lessons)
    if not raw_rows:
        raise HTTPException(status_code=400, detail="Нет строк для импорта")

    batch_id = str(uuid.uuid4())
    errors: List[Dict[str, Any]] = []
    prepared = []
    cache: Dict[str, Optional[int]] = {}
    for index, raw in enumerate(raw_rows, start=1):
        try:
            row = LessonImportRow(**raw)
        except Exception as exc:
            errors.append({"row": index, "error": str(exc).splitlines()[0]})
            continue
        start = local_to_utc(row.start_time)
        if row.end_time:
            end = local_to_utc(row.end_time)
        else:
            end = start + timedelta(minutes=row.duration_minutes or 90)
        if end <= start:
            errors.append({"row": index, "error": "Конец занятия раньше начала"})
            continue
        group_ids = list(request.default_group_ids)
        if row.group:
            group_id = await _resolve_group(db, row.group, cache)
            if group_id is None:
                errors.append({"row": index, "error": f"Группа «{row.group}» не найдена"})
                continue
            group_ids.append(group_id)
        prepared.append((row, start, end, sorted(set(group_ids))))

    if request.dry_run:
        return {"batch_id": None, "dry_run": True, "valid": len(prepared), "errors": errors}

    lesson_ids = []
    for row, start, end, group_ids in prepared:
        lesson = Lesson(
            name=row.name,
            location=row.location,
            start_time=start,
            end_time=end,
            reward_coins=row.reward_coins,
            reward_intelligence_points=row.reward_intelligence,
            reward_satisfaction=row.reward_satisfaction,
            created_by=request.created_by,
            qr_secret=codes.new_secret(),
            source=TEST_SOURCE,
            is_simulated=request.is_simulated,
            import_batch_id=batch_id,
        )
        db.add(lesson)
        await db.flush()
        if group_ids:
            await db.execute(insert(lesson_groups).values(
                [{"lesson_id": lesson.id, "group_id": gid} for gid in group_ids]
            ))
        lesson_ids.append(lesson.id)
    await db.commit()
    return {"batch_id": batch_id, "created": len(lesson_ids), "lesson_ids": lesson_ids, "errors": errors}


@router.delete("/lessons/import/{batch_id}", dependencies=[Depends(require_admin)])
async def delete_import_batch(batch_id: str, db: AsyncSession = Depends(get_db)):
    """Удалить занятия одной тестовой выгрузки"""
    result = await db.execute(delete(Lesson).where(and_(
        Lesson.import_batch_id == batch_id, Lesson.source == TEST_SOURCE
    )))
    await db.commit()
    return {"batch_id": batch_id, "deleted": result.rowcount or 0}


@router.post("/lessons/demo-seed", dependencies=[Depends(require_admin)])
async def demo_seed(request: DemoSeedRequest, db: AsyncSession = Depends(get_db)):
    """
    Демо для защиты: занятие, идущее прямо сейчас (для отметки), и занятие,
    закончившееся 20 минут назад (для демонстрации пропуска и «заморозки»).
    """
    if (await db.execute(select(StudentGroup.id).where(StudentGroup.id == request.group_id))).scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Группа не найдена")
    now = utcnow()
    specs = [
        ("Демо: Математический анализ", now - timedelta(minutes=10), now + timedelta(minutes=80), "А-250"),
        ("Демо: Основы программирования", now - timedelta(minutes=110), now - timedelta(minutes=20), "Б-114"),
    ]
    batch_id = str(uuid.uuid4())
    ids = []
    for name, start, end, location in specs:
        lesson = Lesson(
            name=name, location=location, start_time=start, end_time=end,
            reward_coins=5, reward_intelligence_points=15, reward_satisfaction=8,
            created_by=request.created_by, qr_secret=codes.new_secret(),
            source=TEST_SOURCE, is_simulated=True, import_batch_id=batch_id,
        )
        db.add(lesson)
        await db.flush()
        await db.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=request.group_id))
        ids.append(lesson.id)
    await db.commit()
    return {"batch_id": batch_id, "lesson_ids": ids}
