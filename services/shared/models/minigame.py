"""
Мини-игра «Забег до пары» (раннер): забеги и недельные призы группы.
"""
from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from services.shared.database import Base


class GameRun(Base):
    """Один забег. Результат присылает клиент, сервер проверяет правдоподобие и считает очки сам."""
    __tablename__ = "game_runs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    game = Column(String(32), nullable=False, default="runner")
    seed = Column(Integer, nullable=False)
    # Забег с наградой (в пределах дневного лимита попыток) или тренировочный — только в рейтинг
    rewarded = Column(Boolean, nullable=False, default=False)
    # started | finished | rejected | abandoned
    status = Column(String(16), nullable=False, default="started")
    started_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    distance = Column(Integer, nullable=False, default=0)
    coins_collected = Column(Integer, nullable=False, default=0)
    duration_ms = Column(Integer, nullable=False, default=0)
    score = Column(Integer, nullable=False, default=0)
    coins_awarded = Column(Integer, nullable=False, default=0)
    reject_reason = Column(String(160), nullable=True)

    __table_args__ = (
        Index("ix_game_runs_user_started", "user_id", "started_at"),
        Index("ix_game_runs_game_score", "game", "score"),
    )


class GameWeeklyPrize(Base):
    """Призовое место группы за неделю (выдаётся один раз — уникальный ключ)."""
    __tablename__ = "game_weekly_prizes"

    id = Column(Integer, primary_key=True, index=True)
    game = Column(String(32), nullable=False, default="runner")
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    week_start = Column(Date, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    place = Column(Integer, nullable=False)
    score = Column(Integer, nullable=False, default=0)
    coins = Column(Integer, nullable=False, default=0)
    granted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("game", "group_id", "week_start", "place", name="uq_game_weekly_prize_place"),
    )
