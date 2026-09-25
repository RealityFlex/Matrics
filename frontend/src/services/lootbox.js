import { apiPost } from './apiClient.js';

/**
 * Открыть лутбокс за 50 монет
 * @param {number} userId - ID пользователя
 * @returns {Promise<Object>} Результат открытия лутбокса
 */
export function openLootbox(userId) {
  return apiPost('/inventory/lootbox/open', { user_id: userId });
}

