"""
Модели событий и посещаемости
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base


# Связующая таблица для связи событий с группами (many-to-many)
event_groups = Table(
    'event_groups',
    Base.metadata,
    Column('event_id', Integer, ForeignKey('events.id', ondelete='CASCADE'), primary_key=True),
    Column('group_id', Integer, ForeignKey('student_groups.id', ondelete='CASCADE'), primary_key=True)
)


class Event(Base):
    """
    Событие
    """
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    location = Column(String(200), nullable=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False, index=True)
    end_time = Column(DateTime(timezone=True), nullable=True)
    
    max_participants = Column(Integer, nullable=True)  # Максимальное кол-во участников (None = неограничено)
    is_public = Column(Boolean, default=True, nullable=False)
    
    # Награды за посещение
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    
    # QR код для подтверждения посещения
    qr_token = Column(String(100), nullable=True)  # Уникальный токен для QR кода
    qr_token_generated_at = Column(DateTime(timezone=True), nullable=True)  # Время генерации токена
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    groups = relationship("StudentGroup", secondary=event_groups, back_populates="events")
    attendances = relationship("EventAttendance", back_populates="event", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Event(id={self.id}, name='{self.name}', start_time={self.start_time})>"


class EventAttendance(Base):
    """
    Посещение события пользователем
    """
    __tablename__ = "event_attendances"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("events.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    registered_at = Column(DateTime(timezone=True), server_default=func.now())
    attended = Column(Boolean, default=False, nullable=False)  # Реально посетил
    attended_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    event = relationship("Event", back_populates="attendances")
    user = relationship("User", back_populates="event_attendances")

    def __repr__(self):
        return f"<EventAttendance(event_id={self.event_id}, user_id={self.user_id}, attended={self.attended})>"

