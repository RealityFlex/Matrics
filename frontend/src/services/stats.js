import { apiCall } from './apiClient.js';

export function getUserStatistics(userId) {
  return apiCall(`/statistics/stats/users/${userId}/summary`);
}

