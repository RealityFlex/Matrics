"""
Модели социальных взаимодействий
"""
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, Enum, Table
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


class ClanRole(enum.Enum):
    """Роль в клане"""
    LEADER = "leader"
    OFFICER = "officer"
    MEMBER = "member"


class FriendshipStatus(enum.Enum):
    """Статус дружбы"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    BLOCKED = "blocked"


class GroupInvitationStatus(enum.Enum):
    """Статус приглашения в группу"""
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Clan(Base):
    """
    Клан
    """
    __tablename__ = "clans"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    tag = Column(String(10), nullable=True, unique=True)  # Тег клана [TAG]
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    members = relationship("ClanMember", back_populates="clan", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Clan(id={self.id}, name='{self.name}')>"


class ClanMember(Base):
    """
    Член клана
    """
    __tablename__ = "clan_members"

    id = Column(Integer, primary_key=True, index=True)
    clan_id = Column(Integer, ForeignKey("clans.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(Enum(ClanRole), default=ClanRole.MEMBER, nullable=False)
    
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    clan = relationship("Clan", back_populates="members")
    user = relationship("User", back_populates="clan_memberships")

    def __repr__(self):
        return f"<ClanMember(clan_id={self.clan_id}, user_id={self.user_id}, role={self.role.value})>"


class Friendship(Base):
    """
    Дружба между пользователями
    """
    __tablename__ = "friendships"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    friend_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(FriendshipStatus), default=FriendshipStatus.PENDING, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    accepted_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="friendships_initiated")
    friend = relationship("User", foreign_keys=[friend_id], back_populates="friendships_received")

    def __repr__(self):
        return f"<Friendship(user_id={self.user_id}, friend_id={self.friend_id}, status={self.status.value})>"


class StudentGroup(Base):
    """
    Учебная группа
    """
    __tablename__ = "student_groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    creator_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)

    # Подключение вуза: организация, ссылки-приглашения, чат группы в MAX, командная цель
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True, index=True)
    invite_code = Column(String(16), nullable=True, unique=True)         # вступление студентов: startapp=join-<код>
    curator_code = Column(String(16), nullable=True, unique=True)        # роль куратора: startapp=cur-<код>
    max_chat_id = Column(BigInteger, nullable=True, index=True)          # групповой чат MAX, привязанный через /bindgroup
    team_goal_percent = Column(Integer, nullable=False, default=80, server_default="80")
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    members = relationship("GroupMember", back_populates="group", cascade="all, delete-orphan")
    invitations = relationship("GroupInvitation", back_populates="group", cascade="all, delete-orphan")
    lessons = relationship("Lesson", secondary="lesson_groups", back_populates="groups")
    events = relationship("Event", secondary="event_groups", back_populates="groups")

    def __repr__(self):
        return f"<StudentGroup(id={self.id}, name='{self.name}', creator_id={self.creator_id})>"


class GroupMember(Base):
    """
    Член учебной группы
    """
    __tablename__ = "group_members"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    group = relationship("StudentGroup", back_populates="members")
    user = relationship("User", back_populates="group_memberships")

    def __repr__(self):
        return f"<GroupMember(group_id={self.group_id}, user_id={self.user_id})>"


class GroupInvitation(Base):
    """
    Приглашение в учебную группу
    """
    __tablename__ = "group_invitations"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    inviter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(Enum(GroupInvitationStatus), default=GroupInvitationStatus.PENDING, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    group = relationship("StudentGroup", back_populates="invitations")
    user = relationship("User", foreign_keys=[user_id], back_populates="group_invitations_received")
    inviter = relationship("User", foreign_keys=[inviter_id], back_populates="group_invitations_sent")

    def __repr__(self):
        return f"<GroupInvitation(id={self.id}, group_id={self.group_id}, user_id={self.user_id}, status={self.status.value})>"



# Кураторы учебных групп (роль users.role = 'curator'); используется дашбордом куратора
group_curators = Table(
    "group_curators",
    Base.metadata,
    Column("group_id", Integer, ForeignKey("student_groups.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
)


class Organization(Base):
    """
    Образовательная организация (вуз, колледж). Сеты окружения с organization_id
    видны только её студентам — брендирование под конкретный вуз.
    """
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    short_name = Column(String(50), nullable=True)
    city = Column(String(100), nullable=True)
    brand_color = Column(String(9), nullable=True)   # #RRGGBB
    theme_id = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
