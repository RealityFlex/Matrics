import { apiCall, apiPost, apiDelete } from './apiClient.js';

export function listShopListings({ activeOnly = true } = {}) {
  const params = new URLSearchParams();
  if (activeOnly) {
    params.set('active_only', 'true');
  }
  const query = params.toString();
  return apiCall(`/economy/shop/listings/${query ? `?${query}` : ''}`);
}

/**
 * Выложить предмет в магазин
 * @param {Object} listingData - Данные листинга
 * @param {number} listingData.seller_id - ID продавца (опционально, для пользовательских товаров)
 * @param {number} listingData.item_id - ID предмета
 * @param {number} listingData.price - Цена
 * @param {number|null} listingData.stock - Количество (опционально)
 * @param {boolean} listingData.is_active - Активен ли товар
 */
export function createShopListing(listingData) {
  return apiPost('/economy/shop/listings/', listingData);
}

/**
 * Купить предмет из магазина
 * @param {number} listingId - ID листинга
 * @param {Object} purchaseData - Данные покупки
 * @param {number} purchaseData.user_id - ID покупателя
 * @param {number} purchaseData.quantity - Количество
 */
export function purchaseShopListing(listingId, purchaseData) {
  return apiPost(`/economy/shop/listings/${listingId}/purchase`, purchaseData);
}

/**
 * Отменить размещение товара в магазине (предмет вернется в инвентарь)
 * @param {number} listingId - ID листинга
 */
export function cancelShopListing(listingId) {
  return apiDelete(`/economy/shop/listings/${listingId}`);
}

/**
 * Получить свои товары в магазине (фильтрует на клиенте)
 * @param {number} sellerId - ID продавца
 * @param {Object} options - Опции
 * @param {boolean} options.activeOnly - Только активные товары
 */
export async function getMyShopListings(sellerId, { activeOnly = true } = {}) {
  const listings = await listShopListings({ activeOnly });
  return Array.isArray(listings)
    ? listings.filter((listing) => listing.seller_id === sellerId)
    : [];
}

