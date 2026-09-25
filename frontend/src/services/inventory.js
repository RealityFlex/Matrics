import { apiCall, apiPost } from './apiClient.js';

export function getUserInventory(userId) {
  return apiCall(`/inventory/users/${userId}`);
}

export function getItem(itemId) {
  return apiCall(`/inventory/items/${itemId}`);
}

export function useInventoryItem(userId, itemId) {
  return apiPost(`/inventory/users/${userId}/items/${itemId}/use`);
}

