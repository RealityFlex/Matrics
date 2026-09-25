import React from 'react';
import { ShopListingCard } from './ShopListingCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function ShopList({
  listings,
  itemsMap,
  sellersMap,
  currentUserId,
  isLoading,
  error,
  onRetry,
  onPurchase,
  onCancel,
  processingListingId
}) {
  if (isLoading) {
    return (
      <div id="shopList">
        <StateView state="loading" message="Загрузка товаров…" compact />
      </div>
    );
  }

  if (error) {
    return (
      <div id="shopList">
        <StateView state="error" title="Не удалось загрузить магазин" message={error} onRetry={onRetry} compact />
      </div>
    );
  }

  if (!listings.length) {
    return (
      <div id="shopList">
        <StateView
          state="empty"
          title="Товаров пока нет"
          message="Выставить свой предмет можно из инвентаря кнопкой «Продать»."
          compact
        />
      </div>
    );
  }

  return (
    <div className="shop-grid" id="shopList">
      {listings.map((listing) => (
        <ShopListingCard
          key={listing.id}
          listing={listing}
          item={itemsMap[listing.item_id]}
          seller={listing.seller_id ? sellersMap[listing.seller_id] : null}
          currentUserId={currentUserId}
          onPurchase={onPurchase}
          onCancel={onCancel}
          isProcessing={processingListingId === listing.id}
        />
      ))}
    </div>
  );
}
