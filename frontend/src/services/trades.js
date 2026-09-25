import { apiCall, apiPost, apiDelete } from './apiClient.js';

/**
 * Создать предложение обмена
 * @param {number} initiatorId - ID инициатора обмена
 * @param {Object} tradeData - Данные обмена
 * @param {number} tradeData.recipient_id - ID получателя
 * @param {number|null} tradeData.initiator_item_id - ID предмета инициатора (опционально)
 * @param {number} tradeData.initiator_quantity - Количество предметов инициатора
 * @param {number|null} tradeData.requested_item_id - ID запрашиваемого предмета (опционально)
 * @param {number} tradeData.requested_quantity - Количество запрашиваемых предметов
 * @param {string} [tradeData.comment] - Комментарий к обмену
 */
export function createTradeRequest(initiatorId, tradeData) {
  return apiPost(`/inventory/trades/?initiator_id=${initiatorId}`, tradeData);
}

/**
 * Получить входящие предложения обмена
 * @param {number} userId - ID пользователя
 * @param {string|null} status - Статус для фильтрации (опционально)
 */
export function getReceivedTradeRequests(userId, status = null) {
  let url = `/inventory/trades/users/${userId}/received`;
  if (status) {
    url += `?status=${status}`;
  }
  return apiCall(url);
}

/**
 * Получить отправленные предложения обмена
 * @param {number} userId - ID пользователя
 * @param {string|null} status - Статус для фильтрации (опционально)
 */
export function getSentTradeRequests(userId, status = null) {
  let url = `/inventory/trades/users/${userId}/sent`;
  if (status) {
    url += `?status=${status}`;
  }
  return apiCall(url);
}

/**
 * Принять предложение обмена
 * @param {number} tradeId - ID предложения обмена
 */
export function acceptTradeRequest(tradeId) {
  return apiPost(`/inventory/trades/${tradeId}/accept`, {});
}

/**
 * Отклонить предложение обмена
 * @param {number} tradeId - ID предложения обмена
 */
export function rejectTradeRequest(tradeId) {
  return apiPost(`/inventory/trades/${tradeId}/reject`, {});
}

/**
 * Отменить предложение обмена (только инициатор)
 * @param {number} tradeId - ID предложения обмена
 * @param {number} userId - ID пользователя (инициатора)
 */
export function cancelTradeRequest(tradeId, userId) {
  return apiDelete(`/inventory/trades/${tradeId}?user_id=${userId}`);
}

/**
 * Получить инвентарь пользователя для просмотра при создании запроса на обмен
 * @param {number} userId - ID пользователя, запрашивающего инвентарь
 * @param {number} targetUserId - ID пользователя, чей инвентарь нужно просмотреть
 */
export function getUserInventoryForTrade(userId, targetUserId) {
  return apiCall(`/inventory/trades/users/${userId}/inventory/${targetUserId}`);
}




