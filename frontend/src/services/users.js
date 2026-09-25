import { apiCall, apiPost, apiPut } from './apiClient.js';

export function listUsers() {
  return apiCall('/users/?limit=1000');
}

export function createUser(payload) {
  return apiPost('/users/', payload);
}

export function getUser(userId) {
  return apiCall(`/users/${userId}`);
}

export function updateUser(userId, payload) {
  return apiPut(`/users/${userId}`, payload);
}

export function getUserInventory(userId) {
  return apiCall(`/inventory/users/${userId}`);
}

export function getUserStats(userId) {
  return apiCall(`/statistics/users/${userId}`);
}


/** Вход из мини-приложения MAX по подписанному initData (находит или создаёт пользователя) */
export function authWithMax(initData) {
  return apiPost('/users/auth/max', { init_data: initData });
}

export function getUserByMaxId(maxUserId) {
  return apiCall(`/users/by-max/${maxUserId}`);
}

/** Ник бота и ссылка на него — для «Поделиться» и приглашений */
export function getAppConfig() {
  return apiCall('/users/app-config');
}

/** Вступить в группу (join-КОД) или стать куратором (cur-КОД) по ссылке-приглашению */
export function joinByCode(userId, code) {
  return apiPost(`/users/join?user_id=${userId}`, { code });
}
