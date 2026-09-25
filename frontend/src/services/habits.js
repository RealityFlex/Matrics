import { apiCall, apiDelete, apiPost, apiPut } from './apiClient.js';

export function getHabits(userId) {
  return apiCall(`/habits/user/${userId}`);
}

export function createHabit(userId, payload) {
  return apiPost(`/habits/?user_id=${userId}`, payload);
}

export function updateHabit(habitId, payload) {
  return apiPut(`/habits/${habitId}`, payload);
}

export function deleteHabit(habitId) {
  return apiDelete(`/habits/${habitId}`);
}

export function completeHabit(habitId, notes = 'Выполнено!') {
  return apiPost(`/habits/${habitId}/complete`, { notes });
}

export function skipHabit(habitId) {
  return apiPost(`/habits/${habitId}/skip`);
}

export function getHabit(habitId) {
  return apiCall(`/habits/${habitId}`);
}

export function getHabitStats(habitId) {
  return apiCall(`/habits/${habitId}/stats`);
}

