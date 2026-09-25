import { apiCall, apiPost, authHeaders, getApiBase } from './apiClient.js';

// Кабинет куратора в мини-приложении MAX. Доступ проверяет сервер:
// в MAX — по подписанному initData и роли curator, в веб-демо — по ?user_id (AUTH_MODE=lenient).
const q = (userId) => (userId ? `user_id=${userId}` : '');

export function curatorGroups(userId) {
  return apiCall(`/statistics/stats/curator/groups?${q(userId)}`);
}

export function groupLessons(groupId, userId) {
  return apiCall(`/statistics/stats/curator/groups/${groupId}/lessons?${q(userId)}`);
}

export function groupAttendance(groupId, userId, days = 30) {
  const from = new Date(Date.now() - days * 86400000).toISOString();
  return apiCall(`/statistics/stats/curator/groups/${groupId}/attendance?date_from=${encodeURIComponent(from)}&${q(userId)}`);
}

export function groupAtRisk(groupId, userId) {
  return apiCall(`/statistics/stats/curator/groups/${groupId}/at-risk?${q(userId)}`);
}

export function groupSupport(groupId, userId) {
  return apiCall(`/statistics/stats/curator/groups/${groupId}/support?${q(userId)}`);
}

export function resolveSupport(requestId, userId) {
  return apiPost(`/statistics/stats/curator/support/${requestId}/resolve?${q(userId)}`);
}

export function nudgeStudent(studentId, userId) {
  return apiPost(`/statistics/stats/curator/students/${studentId}/nudge?${q(userId)}`);
}

export function groupInvite(groupId, userId) {
  return apiCall(`/users/groups/${groupId}/invite?${q(userId)}`);
}

export function lessonCode(lessonId, userId) {
  return apiCall(`/events/lessons/${lessonId}/qr?${q(userId)}`);
}

async function imageUrl(path) {
  const response = await fetch(`${getApiBase()}${path}`, { headers: authHeaders() });
  if (!response.ok) {
    throw new Error(`QR не загружен (HTTP ${response.status})`);
  }
  return URL.createObjectURL(await response.blob());
}

/** PNG QR-кода текущего кода пары (object URL — не забудьте revokeObjectURL) */
export function lessonQrImage(lessonId, userId) {
  return imageUrl(`/events/lessons/${lessonId}/qr-image?${q(userId)}`);
}

/** PNG QR-кода произвольной ссылки max.ru (приглашение в группу) */
export function linkQrImage(link, userId) {
  return imageUrl(`/users/qr?data=${encodeURIComponent(link)}&${q(userId)}`);
}
