"""
Демо-данные для проверки и защиты (СМОДЕЛИРОВАННЫЕ ДАННЫЕ, не реальные студенты).

Создаёт учебную группу «ИВТ-11 (демо)», 10 студентов с персонажами, куратора,
историю занятий за 3 недели (посещения, снимки настроения, журнал наград),
пару, идущую прямо сейчас, и пропуск, ожидающий решения («день без штрафа»).

Запуск (стек поднят через docker compose):
    docker compose exec user-service python -m scripts.seed_demo
    docker compose exec user-service python -m scripts.seed_demo --reset   # пересоздать демо
"""
from __future__ import annotations

import argparse
import asyncio
import random
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, insert, select

import services.shared.models  # noqa: F401 — регистрирует все модели
from services.shared.database import AsyncSessionLocal, init_db
from services.shared.migrations import apply_hackathon_migrations
from services.shared.models.character import Character, CharacterSnapshot
from services.shared.models.economy import Transaction, TransactionType
from services.shared.models.lesson import Lesson, LessonAttendance, LessonMiss, LessonMissStatus, VerificationMethod, lesson_groups
from services.shared.models.social import GroupMember, Organization, StudentGroup, group_curators
from services.shared.models.appearance import AppearanceSet
from services.shared.models.minigame import GameRun
from services.shared.models.user import User

GROUP_NAME = "ИВТ-11 (демо)"
ORG_NAME = "Демо-колледж цифровых технологий"
DEMO_PREFIX = "demo_"
SUBJECTS = ["Математический анализ", "Основы программирования", "История России", "Английский язык"]
ROOMS = ["А-250", "Б-114", "В-301", "Г-12"]

# username, отображаемое имя персонажа, вероятность посещения, итоговое настроение
STUDENTS = [
    ("demo_student", "Герой демо", 0.9, 62),
    ("demo_anna", "Анна", 0.95, 88),
    ("demo_ivan", "Иван", 0.35, 18),       # риск: мало ходит, низкое настроение
    ("demo_maria", "Мария", 0.85, 74),
    ("demo_oleg", "Олег", 0.55, 34),       # риск: падение настроения
    ("demo_sofia", "София", 1.0, 92),
    ("demo_timur", "Тимур", 0.75, 58),
    ("demo_elena", "Елена", 0.8, 66),
    ("demo_pavel", "Павел", 0.45, 27),     # риск
    ("demo_daria", "Дарья", 0.9, 80),
]


async def reset(session) -> None:
    group_id = (await session.execute(select(StudentGroup.id).where(StudentGroup.name == GROUP_NAME))).scalar()
    if group_id:
        lesson_ids = (await session.execute(
            select(lesson_groups.c.lesson_id).where(lesson_groups.c.group_id == group_id)
        )).scalars().all()
        if lesson_ids:
            await session.execute(delete(Lesson).where(Lesson.id.in_(lesson_ids)))
        await session.execute(delete(StudentGroup).where(StudentGroup.id == group_id))
    org_id = (await session.execute(select(Organization.id).where(Organization.name == ORG_NAME))).scalar()
    if org_id:
        await session.execute(delete(AppearanceSet).where(AppearanceSet.organization_id == org_id))
        await session.execute(delete(Organization).where(Organization.id == org_id))
    await session.execute(delete(User).where(User.username.like(f"{DEMO_PREFIX}%")))
    await session.commit()


async def seed(force: bool) -> None:
    await init_db()
    await apply_hackathon_migrations()
    rng = random.Random(42)
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        exists = (await session.execute(select(StudentGroup.id).where(StudentGroup.name == GROUP_NAME))).scalar()
        if exists and not force:
            print(f"Демо-группа уже есть (id={exists}). Для пересоздания: --reset")
            return
        await reset(session)

        curator = User(username="demo_curator", email="demo_curator@matrix.local", role="curator", coins=0)
        session.add(curator)
        await session.flush()
        session.add(Character(user_id=curator.id, name="Куратор", satisfaction=70, last_satisfaction_decay=now))

        org = Organization(name=ORG_NAME, short_name="ДКЦТ", city="Казань", brand_color="#6D28D9", theme_id="brand-demo")
        session.add(org)
        await session.flush()
        session.add(AppearanceSet(kind="environment", code=f"brand_org{org.id}", name="Кампус ДКЦТ",
                                  description="Фирменная локация колледжа — доступна его студентам",
                                  asset_key="environment:brand", unlock_type="none", unlock_value=0,
                                  theme_id=org.brand_color, organization_id=org.id, sort_order=5))
        group = StudentGroup(name=GROUP_NAME, description="Смоделированная группа для демонстрации", creator_id=curator.id,
                             organization_id=org.id, invite_code="DEMO2026", curator_code="CURDEMO2026")
        session.add(group)
        await session.flush()
        await session.execute(insert(group_curators).values(group_id=group.id, user_id=curator.id))

        students = []
        for username, name, attend_p, final_sat in STUDENTS:
            user = User(username=username, email=f"{username}@matrix.local", coins=rng.randint(40, 220))
            session.add(user)
            await session.flush()
            session.add(GroupMember(group_id=group.id, user_id=user.id, joined_at=now - timedelta(days=40)))
            level = 1 + int(attend_p * 4)
            session.add(Character(
                user_id=user.id, name=name, satisfaction=final_sat, intelligence_level=level,
                intelligence_points=rng.randint(0, level * 100 - 1), last_satisfaction_decay=now,
            ))
            students.append((user, attend_p, final_sat))

        # История: 3 недели, 4 пары в неделю (пн, вт, чт, пт в 09:00 по Москве = 06:00 UTC)
        start_monday = (now - timedelta(days=now.weekday() + 21)).replace(hour=6, minute=0, second=0, microsecond=0)
        batch_id = "demo-" + secrets.token_hex(4)
        for week in range(3):
            for index, day in enumerate((0, 1, 3, 4)):
                start = start_monday + timedelta(weeks=week, days=day)
                if start + timedelta(minutes=90) > now - timedelta(hours=1):
                    continue
                lesson = Lesson(
                    name=SUBJECTS[index], location=ROOMS[index], start_time=start, end_time=start + timedelta(minutes=90),
                    reward_coins=5, reward_intelligence_points=15, reward_satisfaction=8, created_by=curator.id,
                    qr_secret=secrets.token_hex(16), source="test_import", is_simulated=True, import_batch_id=batch_id,
                )
                session.add(lesson)
                await session.flush()
                await session.execute(insert(lesson_groups).values(lesson_id=lesson.id, group_id=group.id))
                for user, attend_p, _ in students:
                    # Студенты «в зоне риска» к третьей неделе ходят реже
                    probability = attend_p if week < 2 or attend_p > 0.6 else attend_p * 0.5
                    if rng.random() < probability:
                        session.add(LessonAttendance(
                            lesson_id=lesson.id, user_id=user.id, attended_at=start + timedelta(minutes=5),
                            verification_method=VerificationMethod.QR_CODE, rewards_granted_at=start + timedelta(minutes=5),
                        ))
                        session.add(Transaction(
                            user_id=user.id, type=TransactionType.REWARD, amount=5,
                            description="монеты +5, интеллект +15, удовлетворение +8",
                            source="lesson_attendance", source_ref=f"lesson:{lesson.id}", created_at=start + timedelta(minutes=5),
                        ))

        # Ежедневные снимки настроения за 21 день (для «падения настроения» у куратора)
        for user, attend_p, final_sat in students:
            start_sat = 70 if final_sat < 40 else final_sat - rng.randint(-5, 10)
            for days_ago in range(21, -1, -1):
                progress = (21 - days_ago) / 21
                satisfaction = int(start_sat + (final_sat - start_sat) * progress + rng.randint(-3, 3))
                session.add(CharacterSnapshot(
                    user_id=user.id, snapshot_date=(now - timedelta(days=days_ago)).date(),
                    satisfaction=max(0, min(100, satisfaction)), intelligence_level=1 + int(attend_p * 4),
                    intelligence_points=0, coins=user.coins,
                ))

        # Мини-игра «Забег до пары»: результаты этой и прошлой недели (итоги прошлой недели
        # подводятся при первом открытии главного экрана — призы и пост в чат группы)
        for user, attend_p, _ in students[1:]:
            for weeks_ago in (0, 1):
                if rng.random() < 0.8:
                    distance = rng.randint(250, 1400)
                    coins = rng.randint(10, distance // 12)
                    session.add(GameRun(
                        user_id=user.id, game="runner", seed=rng.randint(1, 2**31 - 2), rewarded=True,
                        status="finished", started_at=now - timedelta(days=7 * weeks_ago, hours=rng.randint(1, 40)),
                        finished_at=now - timedelta(days=7 * weeks_ago), distance=distance, coins_collected=coins,
                        duration_ms=int(distance / 18 * 1000), score=distance + coins * 5,
                        coins_awarded=min(10, -(-coins // 10)),
                    ))

        # Пара «прямо сейчас» — для демонстрации отметки
        live = Lesson(
            name="Демо: Математический анализ", location="А-250", start_time=now - timedelta(minutes=10),
            end_time=now + timedelta(minutes=80), reward_coins=5, reward_intelligence_points=15, reward_satisfaction=8,
            created_by=curator.id, qr_secret=secrets.token_hex(16), source="test_import", is_simulated=True,
            import_batch_id=batch_id,
        )
        # Закончившаяся пара с пропуском demo_student — для «дня без штрафа»
        missed = Lesson(
            name="Демо: Основы программирования", location="Б-114", start_time=now - timedelta(minutes=110),
            end_time=now - timedelta(minutes=20), reward_coins=5, reward_intelligence_points=15, reward_satisfaction=8,
            created_by=curator.id, qr_secret=secrets.token_hex(16), source="test_import", is_simulated=True,
            import_batch_id=batch_id,
        )
        # Пара через 12 минут — воркер пришлёт напоминание в MAX за 10 минут до начала
        upcoming = Lesson(
            name="Демо: Английский язык", location="Г-12", start_time=now + timedelta(minutes=12),
            end_time=now + timedelta(minutes=102), reward_coins=5, reward_intelligence_points=10, reward_satisfaction=5,
            created_by=curator.id, qr_secret=secrets.token_hex(16), source="test_import", is_simulated=True,
            import_batch_id=batch_id,
        )
        session.add_all([live, missed, upcoming])
        await session.flush()
        await session.execute(insert(lesson_groups).values([
            {"lesson_id": live.id, "group_id": group.id},
            {"lesson_id": missed.id, "group_id": group.id},
            {"lesson_id": upcoming.id, "group_id": group.id},
        ]))
        demo_user = students[0][0]
        for user, _, _ in students[1:]:
            session.add(LessonAttendance(lesson_id=missed.id, user_id=user.id, attended_at=missed.start_time,
                                         verification_method=VerificationMethod.QR_CODE))
        session.add(LessonMiss(lesson_id=missed.id, user_id=demo_user.id, status=LessonMissStatus.PENDING,
                               detected_at=now, decision_deadline=now + timedelta(hours=12)))
        await session.commit()

        print("Демо-данные созданы (смоделированные).")
        print(f"  Группа: {GROUP_NAME} (id={group.id}), студентов: {len(students)}")
        print(f"  Вход в веб-версии: ник demo_student (id={demo_user.id})")
        print(f"  Пара для отметки: «{live.name}» (id={live.id}) — код на экране админки «Пары и события»")
        print(f"  Куратор: demo_curator (id={curator.id}); кабинет «Группы» в приложении, дашборд — админка → «Куратор»")
        print(f"  Организация: {ORG_NAME}; код группы DEMO2026 (join-DEMO2026), код куратора CURDEMO2026")
        print("  Чат группы в MAX: добавьте бота и отправьте /bindgroup CURDEMO2026")


def main() -> None:
    parser = argparse.ArgumentParser(description="Демо-данные «Матрикс» (смоделированные)")
    parser.add_argument("--reset", action="store_true", help="удалить и пересоздать демо-данные")
    args = parser.parse_args()
    asyncio.run(seed(force=args.reset))


if __name__ == "__main__":
    main()
