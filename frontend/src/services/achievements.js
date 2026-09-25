import { apiCall } from './apiClient.js';

export function getUserAchievements(userId) {
  if (!userId) {
    return Promise.resolve([]);
  }
  return apiCall(`/achievements/users/${userId}`);
}

export function listAchievements() {
  return apiCall('/achievements/');
}

export async function checkAchievements(userId, requirementType) {
  if (!userId || !requirementType) {
    return Promise.resolve({ checked: 0, newly_completed: [] });
  }
  return apiCall(`/achievements/users/${userId}/check?requirement_type=${requirementType}`, {
    method: 'POST'
  });
}

