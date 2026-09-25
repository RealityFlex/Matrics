"""
Модель персонажа пользователя
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Date, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy.ext.hybrid import hybrid_property
from services.shared.database import Base


class Character(Base):
    """
    Персонаж пользователя (тамагочи)
    """
    __tablename__ = "characters"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(50), nullable=False)
    
    # Параметры персонажа
    satisfaction = Column(Integer, default=50, nullable=False)  # 0-100
    intelligence_level = Column(Integer, default=1, nullable=False)  # Уровень интеллекта
    intelligence_points = Column(Integer, default=0, nullable=False)  # Очки для повышения уровня
    bonus_points = Column(Integer, default=0, nullable=False)  # Дополнительные бонусные очки для рейтинга
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_satisfaction_decay = Column(DateTime(timezone=True), nullable=True)

    # Кастомизация: активные сеты внешности и окружения (appearance_sets.id).
    # Внешний ключ создаётся миграцией, в модели — простое целое, чтобы не связывать модули.
    active_character_set_id = Column(Integer, nullable=True)
    active_environment_set_id = Column(Integer, nullable=True)

    # Ограничения
    __table_args__ = (
        CheckConstraint('satisfaction >= 0 AND satisfaction <= 100', name='check_satisfaction_range'),
        CheckConstraint('intelligence_level >= 1', name='check_intelligence_level'),
        CheckConstraint('intelligence_points >= 0', name='check_intelligence_points'),
    )

    # Связи
    user = relationship("User", back_populates="character")

    @hybrid_property
    def rating(self) -> float:
        """
        Вычисляемый рейтинг персонажа
        Формула: очки интеллекта + (удовлетворение / 2) + (уровень интеллекта * 100)
        """
        return (
            self.intelligence_points
            + (self.satisfaction / 2)
            + (self.intelligence_level * 100)
        )

    def add_intelligence_points(self, points: int):
        """
        Добавляет очки интеллекта и повышает уровень при необходимости
        Для повышения уровня требуется всё больше очков (level * 100)
        """
        self.intelligence_points = max(0, self.intelligence_points + points)
        
        # Проверяем, достаточно ли очков для повышения уровня
        points_needed = self.intelligence_level * 100
        while self.intelligence_points >= points_needed:
            self.intelligence_points -= points_needed
            self.intelligence_level += 1
            points_needed = self.intelligence_level * 100

    def adjust_satisfaction(self, amount: int):
        """
        Изменяет удовлетворение с учётом ограничений 0-100
        """
        self.satisfaction = max(0, min(100, self.satisfaction + amount))

    def __repr__(self):
        return f"<Character(id={self.id}, name='{self.name}', rating={self.rating})>"



class CharacterSnapshot(Base):
    """
    Ежедневный снимок параметров персонажа (для дашборда куратора: динамика satisfaction).
    """
    __tablename__ = "character_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    snapshot_date = Column(Date, nullable=False, index=True)
    satisfaction = Column(Integer, nullable=False)
    intelligence_level = Column(Integer, nullable=False)
    intelligence_points = Column(Integer, nullable=False)
    coins = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "snapshot_date", name="uq_character_snapshot_user_date"),
    )
