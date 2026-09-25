"""
Модели предметов и инвентаря
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from services.shared.database import Base
import enum


class ItemRarity(enum.Enum):
    """Редкость предмета"""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


class ItemType(enum.Enum):
    """Тип предмета"""
    CONSUMABLE = "consumable"  # Расходуемый
    EQUIPMENT = "equipment"    # Экипировка
    DECORATION = "decoration"  # Декорация
    SPECIAL = "special"        # Специальный


class Item(Base):
    """
    Предмет в системе
    """
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text, nullable=True)
    rarity = Column(Enum(ItemRarity), default=ItemRarity.COMMON, nullable=False)
    type = Column(Enum(ItemType), default=ItemType.CONSUMABLE, nullable=False)
    base_price = Column(Integer, default=0, nullable=False)  # Базовая цена в монетах
    
    # Награды за использование предмета
    reward_coins = Column(Integer, default=0, nullable=False)
    reward_intelligence_points = Column(Integer, default=0, nullable=False)
    reward_satisfaction = Column(Integer, default=0, nullable=False)
    
    # Изображение предмета
    image_filename = Column(String(255), nullable=True)  # Имя файла для справки
    image_data = Column(Text, nullable=True)  # Base64 данные изображения
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    user_items = relationship("UserItem", back_populates="item", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Item(id={self.id}, name='{self.name}', rarity={self.rarity.value})>"


class UserItem(Base):
    """
    Предметы в инвентаре пользователя
    """
    __tablename__ = "user_items"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=False, index=True)
    quantity = Column(Integer, default=1, nullable=False)
    reserved_for_trade_id = Column(Integer, ForeignKey("trade_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    acquired_at = Column(DateTime(timezone=True), server_default=func.now())

    # Связи
    user = relationship("User", back_populates="user_items")
    item = relationship("Item", back_populates="user_items")
    reserved_for_trade = relationship("TradeRequest", foreign_keys=[reserved_for_trade_id])

    def __repr__(self):
        return f"<UserItem(user_id={self.user_id}, item_id={self.item_id}, quantity={self.quantity}, reserved_for_trade_id={self.reserved_for_trade_id})>"


class TradeStatus(enum.Enum):
    """Статус запроса на обмен"""
    PENDING = "pending"      # Ожидает ответа
    ACCEPTED = "accepted"     # Принят
    REJECTED = "rejected"     # Отклонен
    CANCELLED = "cancelled"   # Отменен


class TradeRequest(Base):
    """
    Запрос на обмен предметами
    """
    __tablename__ = "trade_requests"

    id = Column(Integer, primary_key=True, index=True)
    initiator_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    recipient_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Предмет, который предлагает инициатор (может быть None для обмена без предмета)
    initiator_item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=True, index=True)
    initiator_quantity = Column(Integer, default=1, nullable=False)
    
    # Предмет, который хочет получить инициатор (может быть None для обмена без предмета)
    requested_item_id = Column(Integer, ForeignKey("items.id", ondelete="CASCADE"), nullable=True, index=True)
    requested_quantity = Column(Integer, default=1, nullable=False)
    
    status = Column(Enum(TradeStatus), default=TradeStatus.PENDING, nullable=False)
    comment = Column(Text, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    initiator = relationship("User", foreign_keys=[initiator_id], back_populates="trade_requests_initiated")
    recipient = relationship("User", foreign_keys=[recipient_id], back_populates="trade_requests_received")
    initiator_item = relationship("Item", foreign_keys=[initiator_item_id])
    requested_item = relationship("Item", foreign_keys=[requested_item_id])

    def __repr__(self):
        return f"<TradeRequest(id={self.id}, initiator_id={self.initiator_id}, recipient_id={self.recipient_id}, status={self.status.value})>"
