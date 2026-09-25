import React, { useCallback, useEffect, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import { listShopListings, purchaseShopListing, cancelShopListing } from '../../services/shop.js';
import { getItem } from '../../services/inventory.js';
import { getUser } from '../../services/users.js';
import { ShopList } from './components/ShopList.jsx';
import { toast } from '../../components/ui/toast.jsx';
import '../../styles/features-core.css';

export function ShopSection({ isActive }) {
  const { user } = useAppState();
  
  const [listings, setListings] = useState([]);
  const [itemsMap, setItemsMap] = useState({});
  const [sellersMap, setSellersMap] = useState({});
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [processingListingId, setProcessingListingId] = useState(null);

  const loadListings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await listShopListings();
      const listingsArray = Array.isArray(data) ? data : [];
      setListings(listingsArray);

      // Загружаем информацию о предметах и продавцах
      const items = {};
      const sellers = {};
      const sellerIds = new Set();
      
      listingsArray.forEach((listing) => {
        if (listing.seller_id) {
          sellerIds.add(listing.seller_id);
        }
      });

      await Promise.all([
        // Загружаем предметы
        ...listingsArray.map(async (listing) => {
          try {
            const item = await getItem(listing.item_id);
            items[listing.item_id] = item;
          } catch (err) {
            console.error(`Ошибка загрузки предмета ${listing.item_id}:`, err);
            items[listing.item_id] = null;
          }
        }),
        // Загружаем продавцов
        ...Array.from(sellerIds).map(async (sellerId) => {
          try {
            const seller = await getUser(sellerId);
            sellers[sellerId] = seller;
          } catch (err) {
            console.error(`Ошибка загрузки продавца ${sellerId}:`, err);
            sellers[sellerId] = null;
          }
        })
      ]);
      
      setItemsMap(items);
      setSellersMap(sellers);
    } catch (loadError) {
      console.error('Ошибка загрузки магазина:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить магазин');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadListings();
    }
  }, [isActive]); // Убрали loadListings из зависимостей (не зависит от user)

  const handlePurchase = useCallback(async (listingId) => {
    if (!user?.id) {
      toast.error('Покупка недоступна', 'Необходимо войти в систему');
      return;
    }
    setProcessingListingId(listingId);
    try {
      await purchaseShopListing(listingId, {
        user_id: user.id,
        quantity: 1
      });
      toast.success('Покупка совершена', 'Предмет добавлен в инвентарь');
      await loadListings();
    } catch (purchaseError) {
      console.error('Ошибка покупки:', purchaseError);
      toast.error('Не удалось купить предмет', purchaseError.message ?? 'Попробуйте ещё раз');
    } finally {
      setProcessingListingId(null);
    }
  }, [user?.id, loadListings]);

  const handleCancel = useCallback(async (listingId) => {
    setProcessingListingId(listingId);
    try {
      await cancelShopListing(listingId);
      await loadListings();
    } catch (cancelError) {
      console.error('Ошибка отмены размещения:', cancelError);
      toast.error('Не удалось снять с продажи', cancelError.message ?? 'Попробуйте ещё раз');
    } finally {
      setProcessingListingId(null);
    }
  }, [loadListings]);

  return (
    <div>
      <div className="section-header">
        <h2>Магазин</h2>
      </div>
      <ShopList
        listings={listings}
        itemsMap={itemsMap}
        sellersMap={sellersMap}
        currentUserId={user?.id}
        isLoading={isLoading}
        error={error}
        onRetry={loadListings}
        onPurchase={handlePurchase}
        onCancel={handleCancel}
        processingListingId={processingListingId}
      />
    </div>
  );
}

