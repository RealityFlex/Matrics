"""
Модели привычек и их отслеживания
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


class HabitFrequency(enum.Enum):
    """Частота выполнения привычки"""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Habit(Base):
    """
    Привычка пользователя
    """
    __tablename__ = "habits"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    frequency = Column(Enum(HabitFrequency), default=HabitFrequency.DAILY, nullable=False)
    target_count = Column(Integer, default=1, nullable=False)  # Целевое количество выполнений
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Награды за выполнение привычки
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=0, nullable=False)

    # Связи
    user = relationship("User", back_populates="habits")
    logs = relationship("HabitLog", back_populates="habit", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Habit(id={self.id}, name='{self.name}', frequency={self.frequency.value})>"


class HabitLog(Base):
    """
    Запись о выполнении привычки
    """
    __tablename__ = "habit_logs"

    id = Column(Integer, primary_key=True, index=True)
    habit_id = Column(Integer, ForeignKey("habits.id", ondelete="CASCADE"), nullable=False, index=True)
    
    completed_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    notes = Column(Text, nullable=True)
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=0, nullable=False)

    # Связи
    habit = relationship("Habit", back_populates="logs")

    def __repr__(self):
        return f"<HabitLog(id={self.id}, habit_id={self.habit_id}, completed_at={self.completed_at})>"

