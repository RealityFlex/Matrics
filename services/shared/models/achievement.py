"""
Модели достижений
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base


class Achievement(Base):
    """
    Достижение в системе
    """
    __tablename__ = "achievements"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    icon = Column(String(200), nullable=True)  # URL иконки
    
    # Условия получения
    requirement_type = Column(String(50), nullable=False)  # tasks_completed, habits_logged, etc.
    requirement_value = Column(Integer, nullable=False)  # Сколько нужно выполнить
    
    # Награды за достижение
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    
    is_hidden = Column(Boolean, default=False, nullable=False)  # Скрытое достижение
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    user_achievements = relationship("UserAchievement", back_populates="achievement", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Achievement(id={self.id}, name='{self.name}')>"


class UserAchievement(Base):
    """
    Достижения пользователя
    """
    __tablename__ = "user_achievements"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    achievement_id = Column(Integer, ForeignKey("achievements.id", ondelete="CASCADE"), nullable=False, index=True)
    
    progress = Column(Integer, default=0, nullable=False)  # Текущий прогресс
    completed = Column(Boolean, default=False, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    awarded_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    user = relationship("User", back_populates="user_achievements")
    achievement = relationship("Achievement", back_populates="user_achievements")

    def __repr__(self):
        return f"<UserAchievement(user_id={self.user_id}, achievement_id={self.achievement_id}, progress={self.progress})>"

