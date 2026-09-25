import React from 'react';
import { ArrowLeftRight, Store, Zap } from 'lucide-react';
import { getItemImageSrc } from '../../../utils/itemPresentation.js';
import { Button } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';

export function InventoryItemCard({
  item,
  quantity,
  icon,
  rarityColor,
  rarityLabel,
  typeLabel,
  onTrade,
  onListInShop,
  onUse,
  isUsing
}) {
  const imageSrc = getItemImageSrc(item);
  const rewards = {
    coins: item.reward_coins ?? item.rewardCoins ?? 0,
    intelligence: item.reward_intelligence_points ?? item.rewardIntelligencePoints ?? 0,
    satisfaction: item.reward_satisfaction ?? item.rewardSatisfaction ?? 0
  };
  const hasRewards = rewards.coins > 0 || rewards.intelligence > 0 || rewards.satisfaction > 0;

  const description =
    item.description && !item.description.trim().toLowerCase().startsWith('редкость')
      ? item.description
      : null;

  return (
    <div className="inventory-item-card">
      <div className="item-icon-large">
        {imageSrc ? <img src={imageSrc} alt={item.name} className="item-icon-image" /> : <span className="item-icon-fallback">{icon}</span>}
        {quantity > 1 ? <span className="item-quantity-badge">×{quantity}</span> : null}
      </div>
      <div className="item-name">{item.name ?? `Предмет #${item.id}`}</div>
      <div className="item-meta">
        <span className="item-rarity" style={{ '--rarity': rarityColor }}>
          {rarityLabel}
        </span>
        <span className="item-type">{typeLabel}</span>
      </div>
      {description ? <div className="item-description">{description}</div> : null}
      {hasRewards ? (
        <div className="item-rewards-block">
          <span className="item-rewards-title">При использовании</span>
          <RewardChips rewards={rewards} />
        </div>
      ) : null}
      <div className="item-actions">
        {onUse && (
          <Button size="sm" block icon={<Zap size={16} />} onClick={() => onUse(item)} loading={isUsing}>
            Использовать
          </Button>
        )}
        {(onTrade || onListInShop) && (
          <div className="item-actions__secondary">
            {onTrade && (
              <Button size="sm" variant="secondary" icon={<ArrowLeftRight size={16} />} onClick={() => onTrade(item, quantity)}>
                Обменять
              </Button>
            )}
            {onListInShop && (
              <Button size="sm" variant="secondary" icon={<Store size={16} />} onClick={() => onListInShop(item, quantity)}>
                Продать
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
