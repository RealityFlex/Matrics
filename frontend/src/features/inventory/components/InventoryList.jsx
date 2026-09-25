import React from 'react';
import { InventoryItemCard } from './InventoryItemCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function InventoryList({ items, isLoading, error, onRetry, onTrade, onListInShop, onUse, usingItemId }) {
  if (isLoading) {
    return (
      <div id="inventoryList">
        <StateView state="loading" message="Загрузка инвентаря…" compact />
      </div>
    );
  }

  if (error) {
    return (
      <div id="inventoryList">
        <StateView state="error" title="Не удалось загрузить инвентарь" message={error} onRetry={onRetry} compact />
      </div>
    );
  }

  if (!items.length) {
    return (
      <div id="inventoryList">
        <StateView
          state="empty"
          title="Инвентарь пуст"
          message="Предметы появятся после открытия лутбокса, покупки в магазине или обмена."
          compact
        />
      </div>
    );
  }

  return (
    <div id="inventoryList" className="inventory-grid">
      {items.map((inventoryItem) => (
        <InventoryItemCard
          key={inventoryItem.uniqueKey}
          {...inventoryItem}
          onTrade={onTrade}
          onListInShop={onListInShop}
          onUse={onUse}
          isUsing={usingItemId === (inventoryItem.item?.id ?? inventoryItem.item_id)}
        />
      ))}
    </div>
  );
}
