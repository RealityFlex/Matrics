"""
Модели занятий и посещаемости
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Table, Boolean, UniqueConstraint, Index, false
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


# Связующая таблица для связи занятий с группами (many-to-many)
lesson_groups = Table(
    'lesson_groups',
    Base.metadata,
    Column('lesson_id', Integer, ForeignKey('lessons.id', ondelete='CASCADE'), primary_key=True),
    Column('group_id', Integer, ForeignKey('student_groups.id', ondelete='CASCADE'), primary_key=True)
)


class VerificationMethod(enum.Enum):
    """Метод подтверждения посещения"""
    QR_CODE = "qr_code"
    MESSAGE = "message"
    MANUAL = "manual"


class Lesson(Base):
    """
    Занятие (пара)
    """
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    location = Column(String(200), nullable=True)
    
    qr_code = Column(String(500), nullable=True)  # QR код для подтверждения (генерируется по запросу)
    qr_token = Column(String(100), nullable=True)  # Уникальный токен для QR кода
    
    # Награды за посещение
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=5, server_default="5", nullable=False)

    # Секрет для вычисления ротируемого кода отметки (TOTP-подобный, см. shared/attendance_codes.py)
    qr_secret = Column(String(64), nullable=True)

    # Происхождение данных: manual — создано вручную, test_import — тестовая выгрузка расписания
    source = Column(String(30), default="manual", server_default="manual", nullable=False)
    is_simulated = Column(Boolean, default=False, server_default=false(), nullable=False)
    import_batch_id = Column(String(36), nullable=True, index=True)
    # Напоминание студентам за 10 минут до начала уже отправлено
    reminder_sent_at = Column(DateTime(timezone=True), nullable=True)
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    groups = relationship("StudentGroup", secondary=lesson_groups, back_populates="lessons")
    attendances = relationship("LessonAttendance", back_populates="lesson", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Lesson(id={self.id}, name='{self.name}')>"


class LessonAttendance(Base):
    """
    Посещение занятия
    """
    __tablename__ = "lesson_attendances"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    attended_at = Column(DateTime(timezone=True), server_default=func.now())
    verification_method = Column(Enum(VerificationMethod), default=VerificationMethod.QR_CODE, nullable=False)
    rewards_granted_at = Column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("lesson_id", "user_id", name="uq_lesson_attendance_lesson_user"),
    )

    # Связи
    lesson = relationship("Lesson", back_populates="attendances")
    user = relationship("User", back_populates="lesson_attendances")

    def __repr__(self):
        return f"<LessonAttendance(lesson_id={self.lesson_id}, user_id={self.user_id})>"



class LessonMissStatus:
    """Статусы пропуска занятия (строки, чтобы не менять enum-типы Postgres)"""
    PENDING = "pending"        # пропуск зафиксирован, ждём решения («заморозить» или штраф)
    FROZEN = "frozen"          # студент взял «день без штрафа»
    PENALIZED = "penalized"    # применён штраф satisfaction
    EXCUSED = "excused"        # уважительная причина (выставляет куратор)


class LessonMiss(Base):
    """
    Пропуск занятия. Используется для серии посещений и «заморозок» (streak freeze).
    """
    __tablename__ = "lesson_misses"

    id = Column(Integer, primary_key=True, index=True)
    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(20), default=LessonMissStatus.PENDING, nullable=False)
    detected_at = Column(DateTime(timezone=True), server_default=func.now())
    decision_deadline = Column(DateTime(timezone=True), nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    satisfaction_penalty = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        UniqueConstraint("lesson_id", "user_id", name="uq_lesson_miss_lesson_user"),
        Index("ix_lesson_misses_user_status", "user_id", "status"),
    )

    def __repr__(self):
        return f"<LessonMiss(lesson_id={self.lesson_id}, user_id={self.user_id}, status={self.status})>"


class LessonGroupGoal(Base):
    """
    Командная цель группы на занятии: когда отметилось team_goal_percent% группы,
    все отметившиеся получают бонус, а в чат группы MAX приходит сообщение.
    """
    __tablename__ = "lesson_group_goals"

    lesson_id = Column(Integer, ForeignKey("lessons.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), primary_key=True)
    achieved_at = Column(DateTime(timezone=True), nullable=True)
    attended = Column(Integer, nullable=False, default=0)
    expected = Column(Integer, nullable=False, default=0)
    summary_sent_at = Column(DateTime(timezone=True), nullable=True)


class SupportRequest(Base):
    """Обращение «Нужна помощь» — передаётся куратору группы (не заменяет специалиста)"""
    __tablename__ = "support_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(30), nullable=False, default="student")   # student | curator_nudge | auto
    message = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default="open")      # open | resolved
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
