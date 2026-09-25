import React from 'react';
import { Ban, Package, ShoppingCart, User } from 'lucide-react';
import {
  getItemIcon,
  getItemImageSrc,
  getRarityColor,
  getRarityLabel,
  getTypeLabel
} from '../../../utils/itemPresentation.js';
import { Badge, Button } from '../../../components/ui/index.jsx';
import { RewardChips, StatValue } from '../../../components/ui/icons.jsx';

function formatListingDate(listing) {
  const raw = listing.listed_at || listing.created_at;
  if (!raw) {
    return null;
  }
  const date = new Date(raw);
  return Number.isNaN(date.getTime()) ? null : date.toLocaleDateString('ru-RU');
}

export function ShopListingCard({
  listing,
  item,
  seller,
  currentUserId,
  onPurchase,
  onCancel,
  isProcessing
}) {
  const isMyListing = listing.seller_id && listing.seller_id === currentUserId;
  const isActive = listing.is_active;
  const stock = listing.stock ?? null;
  const hasStock = stock === null || stock > 0;

  const itemType = item?.type || 'special';
  const imageSrc = item ? getItemImageSrc(item) : null;
  const itemName = item?.name || `Предмет #${listing.item_id}`;
  const itemRarity = item?.rarity || 'common';
  const rarityColor = getRarityColor(itemRarity);
  const rarityLabel = getRarityLabel(itemRarity);
  const dateDisplay = formatListingDate(listing);

  const sellerName = seller
    ? seller.username || `Пользователь #${listing.seller_id}`
    : listing.seller_id
    ? `Пользователь #${listing.seller_id}`
    : 'Система';

  const rewards = {
    coins: item?.reward_coins ?? item?.rewardCoins ?? 0,
    intelligence: item?.reward_intelligence_points ?? item?.rewardIntelligencePoints ?? 0,
    satisfaction: item?.reward_satisfaction ?? item?.rewardSatisfaction ?? 0
  };
  const hasRewards = rewards.coins > 0 || rewards.intelligence > 0 || rewards.satisfaction > 0;

  const canBuy = isActive && hasStock && !isMyListing && onPurchase;
  const canCancel = isMyListing && onCancel;

  return (
    <div className="shop-item-card">
      <div className="item-icon-large">
        {imageSrc ? (
          <img src={imageSrc} alt={itemName} className="item-icon-image" />
        ) : item ? (
          <span className="item-icon-fallback">{getItemIcon(itemType, item.id)}</span>
        ) : (
          <span className="item-icon-fallback">
            <Package size={48} strokeWidth={1.5} aria-hidden="true" />
          </span>
        )}
      </div>
      <div className="fc-card__head">
        <div className="item-name">{itemName}</div>
        {!isActive ? <Badge tone="neutral">Снят с продажи</Badge> : null}
      </div>
      <div className="item-meta">
        <span className="item-rarity" style={{ '--rarity': rarityColor }}>
          {rarityLabel}
        </span>
        {item ? <span className="item-type">{getTypeLabel(itemType)}</span> : null}
      </div>
      {item?.description ? <div className="item-description">{item.description}</div> : null}
      <div className="fc-rows">
        <div className="fc-row">
          <StatValue kind="coins" value={listing.price} />
          <span>монет</span>
        </div>
        <div className="fc-row">
          <Package size={16} aria-hidden="true" className="icon-muted" />
          <span>
            В наличии: <strong>{stock !== null ? stock : 'без ограничений'}</strong>
          </span>
        </div>
        {listing.seller_id ? (
          <div className="fc-row">
            <User size={16} aria-hidden="true" className="icon-muted" />
            <span>
              Продавец: <strong>{isMyListing ? 'вы' : sellerName}</strong>
            </span>
          </div>
        ) : null}
        {dateDisplay ? <div className="fc-row fc-muted">Выставлен {dateDisplay}</div> : null}
      </div>
      {hasRewards ? (
        <div className="item-rewards-block">
          <span className="item-rewards-title">При использовании</span>
          <RewardChips rewards={rewards} />
        </div>
      ) : null}
      {canBuy || canCancel || !hasStock ? (
        <div className="item-actions">
          {canBuy ? (
            <Button
              size="sm"
              block
              icon={<ShoppingCart size={16} />}
              onClick={() => onPurchase(listing.id)}
              loading={isProcessing}
            >
              Купить
            </Button>
          ) : null}
          {canCancel ? (
            <Button
              size="sm"
              variant="secondary"
              block
              icon={<Ban size={16} />}
              onClick={() => onCancel(listing.id)}
              loading={isProcessing}
            >
              Снять с продажи
            </Button>
          ) : null}
          {!hasStock ? <p className="fc-muted">Товар закончился</p> : null}
        </div>
      ) : null}
    </div>
  );
}
