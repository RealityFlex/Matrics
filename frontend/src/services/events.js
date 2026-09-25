import { apiCall, apiPost } from './apiClient.js';

export function listEvents({ upcomingOnly = false, userId = null } = {}) {
  const params = new URLSearchParams();
  if (upcomingOnly) {
    params.set('upcoming_only', 'true');
  }
  if (userId) {
    params.set('user_id', userId.toString());
  }
  const query = params.toString();
  return apiCall(`/events/events/${query ? `?${query}` : ''}`);
}

export function registerForEvent(eventId, userId) {
  return apiPost(`/events/events/${eventId}/register?user_id=${userId}`);
}

export function verifyEventCode(eventId, userId, code) {
  return apiPost(`/events/events/${eventId}/verify-code?user_id=${userId}`, { code });
}

export function getEventCode(eventId) {
  return apiCall(`/events/events/${eventId}/code`);
}

export function getUserEventAttendance(eventId, userId) {
  return apiCall(`/events/events/${eventId}/user/${userId}/attendance`);
}

export function listLessons({ userId = null } = {}) {
  const params = new URLSearchParams();
  if (userId) {
    params.set('user_id', userId.toString());
  }
  const query = params.toString();
  return apiCall(`/events/lessons/${query ? `?${query}` : ''}`);
}

export function verifyLessonCode(lessonId, userId, code) {
  return apiPost(`/events/lessons/${lessonId}/attendance?user_id=${userId}`, { code: code });
}

export async function getUserLessonAttendance(lessonId, userId) {
  try {
    const attendances = await apiCall(`/events/lessons/${lessonId}/attendance`);
    const userAttendance = attendances.find(a => a.user_id === userId);
    return userAttendance || null;
  } catch (error) {
    console.error('Ошибка получения статуса посещения занятия:', error);
    return null;
  }
}


// ---------- Основной сценарий: отметка на занятии ----------

/** Расписание студента: текущее и ближайшее занятие, список на неделю */
export function getSchedule(userId) {
  return apiCall(`/events/schedule/users/${userId}`);
}

/**
 * Отметиться на занятии кодом (method: 'code') или по QR (method: 'qr').
 * Возвращает награды, новое состояние персонажа и серию посещений.
 */
export function checkInLesson(lessonId, userId, code, method = 'code') {
  return apiPost(`/events/lessons/${lessonId}/check-in?user_id=${userId}`, { code, method });
}

/** Серия посещений, остаток «дней без штрафа», пропуски, ожидающие решения */
export function getStreak(userId) {
  return apiCall(`/events/streaks/users/${userId}`);
}

export function freezeMiss(userId, missId) {
  return apiPost(`/events/streaks/users/${userId}/freeze?user_id=${userId}`, { miss_id: missId });
}

/** Разбор payload QR-кода / диплинка: att-<lessonId>-<code> */
export function parseCheckinPayload(value) {
  if (!value) return null;
  const match = String(value).match(/att-(\d{1,10})-(\d{4})/);
  return match ? { lessonId: Number(match[1]), code: match[2] } : null;
}

/** «Нужна помощь?» — обращение уходит куратору группы в MAX */
export function requestSupport(userId, message) {
  return apiPost(`/events/support/request?user_id=${userId}`, { message: message || null });
}
