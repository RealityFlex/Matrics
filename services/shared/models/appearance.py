"""
Модели кастомизации: сеты внешности персонажа и окружения
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, UniqueConstraint, true
from sqlalchemy.sql import func
from services.shared.database import Base


class AppearanceKind:
    CHARACTER = "character"      # внешность персонажа
    ENVIRONMENT = "environment"  # окружение (сцена вокруг персонажа)


class UnlockType:
    NONE = "none"                            # доступно сразу
    COINS = "coins"                          # покупка за монеты
    ATTENDANCE_STREAK = "attendance_streak"  # лучшая серия посещений >= N
    LESSONS_ATTENDED = "lessons_attended"    # посещено занятий >= N
    TASKS_COMPLETED = "tasks_completed"      # выполнено задач >= N
    LEVEL = "level"                          # уровень интеллекта >= N


class AppearanceSet(Base):
    """
    Сет кастомизации. asset_key — ключ визуального пресета во фронтенде
    (или путь к собственной GLB-модели). theme_id/organization_id — задел под
    брендирование сетов для конкретного вуза/колледжа.
    """
    __tablename__ = "appearance_sets"

    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String(20), nullable=False, index=True)
    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    asset_key = Column(String(200), nullable=False)
    unlock_type = Column(String(30), nullable=False, default=UnlockType.NONE)
    unlock_value = Column(Integer, nullable=False, default=0)
    price_coins = Column(Integer, nullable=True)
    theme_id = Column(String(50), nullable=True)
    organization_id = Column(Integer, nullable=True, index=True)
    sort_order = Column(Integer, nullable=False, default=0)
    is_active = Column(Boolean, nullable=False, default=True, server_default=true())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserAppearanceUnlock(Base):
    """Разблокированный пользователем сет"""
    __tablename__ = "user_appearance_unlocks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    set_id = Column(Integer, ForeignKey("appearance_sets.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(20), nullable=False, default="auto")  # default | purchase | auto | admin
    unlocked_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "set_id", name="uq_user_appearance_unlock"),
    )
