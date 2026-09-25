"""
Модели экономики: магазин и транзакции
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


class TransactionType(enum.Enum):
    """Тип транзакции"""
    PURCHASE = "purchase"          # Покупка
    SALE = "sale"                 # Продажа
    REWARD = "reward"             # Награда
    TRANSFER = "transfer"         # Перевод
    TASK_COMPLETION = "task_completion"
    HABIT_LOGGING = "habit_logging"
    EVENT_ATTENDANCE = "event_attendance"


class ShopListing(Base):
    """
    Товар в магазине
    """
    __tablename__ = "shop_listings"

    id = Column(Integer, primary_key=True, index=True)
    seller_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # Продавец (опционально для обратной совместимости)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    price = Column(Integer, nullable=False)  # Цена в монетах
    stock = Column(Integer, nullable=True)  # Количество в наличии (None = неограничено)
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    seller = relationship("User", foreign_keys=[seller_id])
    item = relationship("Item")

    def __repr__(self):
        return f"<ShopListing(id={self.id}, item_id={self.item_id}, price={self.price})>"


class Transaction(Base):
    """
    Финансовая транзакция
    """
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(Enum(TransactionType), nullable=False)
    
    amount = Column(Integer, nullable=False)  # Сумма (может быть отрицательной при тратах)
    description = Column(Text, nullable=True)
    
    # Дополнительные данные
    related_item_id = Column(Integer, ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    related_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Для переводов

    # Источник начисления (lesson_attendance, task_completion, lesson_missed, ...) и ссылка на объект
    source = Column(String(50), nullable=True, index=True)
    source_ref = Column(String(100), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Связи
    user = relationship("User", foreign_keys=[user_id], back_populates="transactions")
    item = relationship("Item", foreign_keys=[related_item_id])
    related_user = relationship("User", foreign_keys=[related_user_id])

    def __repr__(self):
        return f"<Transaction(id={self.id}, user_id={self.user_id}, type={self.type.value}, amount={self.amount})>"

