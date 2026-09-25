"""
Модель пользователя
"""
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base


class User(Base):
    """
    Пользователь системы
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    coins = Column(Integer, default=0, nullable=False)  # Монеты пользователя
    # Роль: student | curator | admin (строка, без enum-типа Postgres)
    role = Column(String(20), default="student", server_default="student", nullable=False)
    last_daily_reward_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    character = relationship("Character", back_populates="user", uselist=False, cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
    habits = relationship("Habit", back_populates="user", cascade="all, delete-orphan")
    user_items = relationship("UserItem", back_populates="user", cascade="all, delete-orphan")
    user_achievements = relationship("UserAchievement", back_populates="user", cascade="all, delete-orphan")
    clan_memberships = relationship("ClanMember", back_populates="user", cascade="all, delete-orphan")
    friendships_initiated = relationship("Friendship", foreign_keys="Friendship.user_id", back_populates="user", cascade="all, delete-orphan")
    friendships_received = relationship("Friendship", foreign_keys="Friendship.friend_id", back_populates="friend", cascade="all, delete-orphan")
    group_memberships = relationship("GroupMember", back_populates="user", cascade="all, delete-orphan")
    group_invitations_received = relationship("GroupInvitation", foreign_keys="GroupInvitation.user_id", back_populates="user", cascade="all, delete-orphan")
    group_invitations_sent = relationship("GroupInvitation", foreign_keys="GroupInvitation.inviter_id", back_populates="inviter", cascade="all, delete-orphan")
    event_attendances = relationship("EventAttendance", back_populates="user", cascade="all, delete-orphan")
    lesson_attendances = relationship("LessonAttendance", back_populates="user", cascade="all, delete-orphan")
    transactions = relationship("Transaction", foreign_keys="Transaction.user_id", back_populates="user", cascade="all, delete-orphan")
    competition_participations = relationship("CompetitionParticipant", back_populates="user", cascade="all, delete-orphan")
    goals = relationship("Goal", back_populates="user", cascade="all, delete-orphan")
    goal_tasks = relationship("GoalTask", back_populates="user", cascade="all, delete-orphan")
    trade_requests_initiated = relationship("TradeRequest", foreign_keys="TradeRequest.initiator_id", back_populates="initiator", cascade="all, delete-orphan")
    trade_requests_received = relationship("TradeRequest", foreign_keys="TradeRequest.recipient_id", back_populates="recipient", cascade="all, delete-orphan")
    # Используем строковое имя для избежания проблем с импортами
    task_generation = relationship("TaskGeneration", back_populates="user", uselist=False, cascade="all, delete-orphan")
    challenges_initiated = relationship("Challenge", foreign_keys="Challenge.challenger_id", back_populates="challenger", cascade="all, delete-orphan")
    challenges_received = relationship("Challenge", foreign_keys="Challenge.opponent_id", back_populates="opponent", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}', email='{self.email}')>"

