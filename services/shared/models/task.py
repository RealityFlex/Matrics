"""
Модель задач
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


class TaskStatus(enum.Enum):
    """Статусы задачи"""
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class TaskPriority(enum.Enum):
    """Приоритет задачи"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class GoalStatus(enum.Enum):
    """Статусы глобальной цели"""
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Task(Base):
    """
    Задача пользователя
    """
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = Column(Enum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Награды за выполнение задачи
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=0, nullable=False)

    # Связи
    user = relationship("User", back_populates="tasks")

    def complete(self):
        """Отметить задачу как выполненную"""
        self.status = TaskStatus.COMPLETED
        self.completed_at = func.now()

    def __repr__(self):
        return f"<Task(id={self.id}, title='{self.title}', status={self.status.value})>"


class Goal(Base):
    """
    Глобальная цель пользователя
    """
    __tablename__ = "goals"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default=GoalStatus.PLANNED.value, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Связи
    user = relationship("User", back_populates="goals")
    tasks = relationship(
        "GoalTask",
        back_populates="goal",
        cascade="all, delete-orphan",
        order_by="GoalTask.order_index"
    )

    def __repr__(self):
        return f"<Goal(id={self.id}, title='{self.title}', status={self.status})>"


class GoalTask(Base):
    """
    Подзадача в рамках глобальной цели
    """
    __tablename__ = "goal_tasks"

    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(32), default=TaskStatus.TODO.value, nullable=False)
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=0, nullable=False)
    order_index = Column(Integer, default=0, nullable=False)
    due_date = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    goal = relationship("Goal", back_populates="tasks")
    user = relationship("User", back_populates="goal_tasks")

    def __repr__(self):
        return f"<GoalTask(id={self.id}, goal_id={self.goal_id}, status={self.status})>"

