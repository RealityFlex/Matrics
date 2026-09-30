"""
Идемпотентная миграция схемы для доработок хакатона (посещаемость, серии,
кастомизация, роли, журнал наград).

Запускается при старте нескольких сервисов (кто стартует первым — тот и применит).
Важно: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` берёт эксклюзивную блокировку
таблицы даже если колонка уже есть, поэтому сначала читаем каталог и выполняем DDL
только для недостающих объектов. Параллельные запуски сериализуются advisory-lock'ом,
а lock_timeout не даёт старту сервиса зависнуть за чужой долгой транзакцией.
Все изменения дублируются в моделях SQLAlchemy — тесты на SQLite создают схему
через metadata.create_all и этот SQL не выполняют.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)

_LOCK_ID = 7340001
_LOCK_TIMEOUT = "5s"
_ATTEMPTS = 6

# (таблица, колонка, определение)
COLUMNS = [
    ("lessons", "reward_satisfaction", "INTEGER NOT NULL DEFAULT 5"),
    ("lessons", "qr_secret", "VARCHAR(64)"),
    ("lessons", "source", "VARCHAR(30) NOT NULL DEFAULT 'manual'"),
    ("lessons", "is_simulated", "BOOLEAN NOT NULL DEFAULT false"),
    ("lessons", "import_batch_id", "VARCHAR(36)"),
    ("lesson_attendances", "rewards_granted_at", "TIMESTAMP WITH TIME ZONE"),
    ("characters", "active_character_set_id", "INTEGER"),
    ("characters", "active_environment_set_id", "INTEGER"),
    ("users", "role", "VARCHAR(20) NOT NULL DEFAULT 'student'"),
    ("transactions", "source", "VARCHAR(50)"),
    ("transactions", "source_ref", "VARCHAR(100)"),
    ("lessons", "reminder_sent_at", "TIMESTAMP WITH TIME ZONE"),
    ("student_groups", "organization_id", "INTEGER"),
    ("student_groups", "invite_code", "VARCHAR(16)"),
    ("student_groups", "curator_code", "VARCHAR(16)"),
    ("student_groups", "max_chat_id", "BIGINT"),
    ("student_groups", "team_goal_percent", "INTEGER NOT NULL DEFAULT 80"),
    ("goal_tasks", "depends_on", "TEXT"),
]

# (имя индекса, DDL)
INDEXES = [
    ("uq_student_groups_invite_code", "CREATE UNIQUE INDEX IF NOT EXISTS uq_student_groups_invite_code ON student_groups (invite_code)"),
    ("uq_student_groups_curator_code", "CREATE UNIQUE INDEX IF NOT EXISTS uq_student_groups_curator_code ON student_groups (curator_code)"),
    ("ix_student_groups_max_chat_id", "CREATE INDEX IF NOT EXISTS ix_student_groups_max_chat_id ON student_groups (max_chat_id)"),
    ("ix_lessons_import_batch_id", "CREATE INDEX IF NOT EXISTS ix_lessons_import_batch_id ON lessons (import_batch_id)"),
    ("ix_transactions_source", "CREATE INDEX IF NOT EXISTS ix_transactions_source ON transactions (source)"),
]

# Уникальность отметки: создаём, только если в данных нет дублей (дубли не удаляем)
UNIQUE_ATTENDANCE_SQL = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM lesson_attendances GROUP BY lesson_id, user_id HAVING COUNT(*) > 1
    ) THEN
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lesson_attendance_lesson_user ON lesson_attendances (lesson_id, user_id);
    ELSE
        RAISE NOTICE 'lesson_attendances содержит дубли — уникальный индекс не создан';
    END IF;
END $$;
"""

FOREIGN_KEYS = [
    ("fk_student_groups_organization",
     "ALTER TABLE student_groups ADD CONSTRAINT fk_student_groups_organization "
     "FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE SET NULL"),
    ("fk_characters_active_character_set",
     "ALTER TABLE characters ADD CONSTRAINT fk_characters_active_character_set "
     "FOREIGN KEY (active_character_set_id) REFERENCES appearance_sets(id) ON DELETE SET NULL"),
    ("fk_characters_active_environment_set",
     "ALTER TABLE characters ADD CONSTRAINT fk_characters_active_environment_set "
     "FOREIGN KEY (active_environment_set_id) REFERENCES appearance_sets(id) ON DELETE SET NULL"),
]

NEW_TABLES = ["lesson_misses", "character_snapshots", "appearance_sets", "user_appearance_unlocks", "group_curators",
              "organizations", "lesson_group_goals", "support_requests", "game_lives"]


def _new_tables():
    import services.shared.models  # noqa: F401 — регистрирует все модели в metadata
    from services.shared.database import Base

    return [Base.metadata.tables[name] for name in NEW_TABLES]


async def _existing(conn, sql: str, params=None) -> set:
    rows = (await conn.execute(text(sql), params or {})).all()
    return {tuple(row) if len(row) > 1 else row[0] for row in rows}


async def _run(conn, statement: str) -> bool:
    try:
        await conn.execute(text(f"SET LOCAL lock_timeout = '{_LOCK_TIMEOUT}'"))
        await conn.execute(text(statement))
        await conn.commit()
        return True
    except Exception as exc:
        await conn.rollback()
        logger.warning("Миграция: команда не выполнена (%s): %s", exc.__class__.__name__, str(exc).splitlines()[0])
        return False


async def _migrate_once(conn) -> bool:
    """Один проход. True — схема в нужном состоянии."""
    from services.shared.database import Base

    ok = True
    existing_columns = await _existing(
        conn,
        "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = current_schema()",
    )
    existing_tables = {table for table, _ in existing_columns}
    for table, column, definition in COLUMNS:
        if table in existing_tables and (table, column) not in existing_columns:
            ok &= await _run(conn, f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {definition}")

    missing_tables = [t for t in _new_tables() if t.name not in existing_tables]
    if missing_tables:
        try:
            await conn.run_sync(lambda sync_conn: Base.metadata.create_all(sync_conn, tables=missing_tables, checkfirst=True))
            await conn.commit()
        except Exception as exc:
            await conn.rollback()
            ok = False
            logger.warning("Миграция: не удалось создать таблицы %s: %s", [t.name for t in missing_tables], exc)

    existing_indexes = await _existing(conn, "SELECT indexname FROM pg_indexes WHERE schemaname = current_schema()")
    for name, ddl in INDEXES:
        if name not in existing_indexes:
            ok &= await _run(conn, ddl)
    if "uq_lesson_attendance_lesson_user" not in existing_indexes and "lesson_attendances" in existing_tables:
        ok &= await _run(conn, UNIQUE_ATTENDANCE_SQL)

    existing_constraints = await _existing(conn, "SELECT conname FROM pg_constraint")
    for name, ddl in FOREIGN_KEYS:
        if name not in existing_constraints:
            ok &= await _run(conn, ddl)
    return ok


async def apply_hackathon_migrations() -> None:
    """Применить миграцию. Никогда не бросает исключение наружу и не зависает."""
    from services.shared.database import engine

    if engine.dialect.name != "postgresql":
        logger.info("Миграция хакатона пропущена: диалект %s", engine.dialect.name)
        return

    for attempt in range(1, _ATTEMPTS + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text(f"SET lock_timeout = '{_LOCK_TIMEOUT}'"))
                locked = (await conn.execute(text(f"SELECT pg_try_advisory_lock({_LOCK_ID})"))).scalar()
                await conn.commit()
                if not locked:
                    logger.info("Миграция хакатона выполняется другим сервисом, ждём (%s/%s)", attempt, _ATTEMPTS)
                    await asyncio.sleep(2)
                    continue
                try:
                    if await _migrate_once(conn):
                        logger.info("Миграция хакатона применена")
                        return
                finally:
                    await conn.execute(text(f"SELECT pg_advisory_unlock({_LOCK_ID})"))
                    await conn.commit()
        except Exception as exc:  # pragma: no cover — зависит от состояния БД
            logger.warning("Миграция хакатона: попытка %s не удалась: %s", attempt, exc)
        await asyncio.sleep(2)
    logger.error("Миграция хакатона применена не полностью — проверьте долгие транзакции в БД")
