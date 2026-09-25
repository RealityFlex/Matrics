"""
Модели соревнований
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


class Competition(Base):
    """
    Соревнование
    """
    __tablename__ = "competitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Метрика соревнования
    metric_type = Column(String(50), nullable=True)  # По какой метрике соревнуются (tasks_completed, habits_completed, coins_balance, intelligence_points)
    target_value = Column(Integer, nullable=True)  # Целевое значение метрики, которое нужно достичь
    
    # Награды
    first_place_coins = Column(Integer, default=0, nullable=False)
    second_place_coins = Column(Integer, default=0, nullable=False)
    third_place_coins = Column(Integer, default=0, nullable=False)
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_finished = Column(Boolean, default=False, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    participants = relationship("CompetitionParticipant", back_populates="competition", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Competition(id={self.id}, name='{self.name}')>"


class CompetitionParticipant(Base):
    """
    Участник соревнования
    """
    __tablename__ = "competition_participants"

    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    score = Column(Integer, default=0, nullable=False)  # Счет участника
    rank = Column(Integer, nullable=True)  # Место в рейтинге
    metric_value = Column(Integer, nullable=True)  # Значение метрики на момент завершения соревнования (учитывается только прогресс после присоединения)
    start_metric_value = Column(Integer, nullable=True)  # Начальное значение метрики при присоединении к соревнованию
    
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    competition = relationship("Competition", back_populates="participants")
    user = relationship("User", back_populates="competition_participations")

    def __repr__(self):
        return f"<CompetitionParticipant(competition_id={self.competition_id}, user_id={self.user_id}, score={self.score})>"


class ChallengeStatus(enum.Enum):
    """
    Статус персонального челленджа
    """
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Challenge(Base):
    """
    Персональное соревнование (челлендж) между двумя пользователями
    """
    __tablename__ = "challenges"

    id = Column(Integer, primary_key=True, index=True)
    challenger_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    opponent_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    metric_type = Column(String(50), nullable=False)  # Какой параметр отслеживаем (например, tasks_completed)
    target_value = Column(Integer, nullable=False)  # До какого значения нужно дойти

    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)

    challenger_start_value = Column(Integer, default=0, nullable=False)
    opponent_start_value = Column(Integer, default=0, nullable=False)

    challenger_progress = Column(Integer, default=0, nullable=False)
    opponent_progress = Column(Integer, default=0, nullable=False)

    deadline = Column(DateTime(timezone=True), nullable=False)

    status = Column(Enum(ChallengeStatus), default=ChallengeStatus.PENDING, nullable=False)
    winner_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    challenger = relationship("User", foreign_keys=[challenger_id], back_populates="challenges_initiated")
    opponent = relationship("User", foreign_keys=[opponent_id], back_populates="challenges_received")
    winner = relationship("User", foreign_keys=[winner_id])

    def __repr__(self):
        return (
            f"<Challenge(id={self.id}, challenger_id={self.challenger_id}, "
            f"opponent_id={self.opponent_id}, status={self.status})>"
        )


class CompetitionDecline(Base):
    """
    Отказ пользователя от участия в соревновании
    """
    __tablename__ = "competition_declines"

    id = Column(Integer, primary_key=True, index=True)
    competition_id = Column(Integer, ForeignKey("competitions.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    declined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    competition = relationship("Competition")
    user = relationship("User")

    def __repr__(self):
        return f"<CompetitionDecline(competition_id={self.competition_id}, user_id={self.user_id})>"

