"""
Модель для отслеживания генерации задач пользователями
"""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base


class TaskGeneration(Base):
    """
    Отслеживание последней генерации задачи пользователем
    """
    __tablename__ = "task_generations"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    last_generated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Уникальное ограничение: один пользователь - одна запись
    __table_args__ = (
        UniqueConstraint('user_id', name='uq_task_generation_user'),
    )
    
    # Связи
    user = relationship("User", back_populates="task_generation")
    
    def __repr__(self):
        return f"<TaskGeneration(user_id={self.user_id}, last_generated_at={self.last_generated_at})>"

