const API_BASE =
  window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
    ? 'http://localhost/api'
    : '/api';

const ADMIN_TOKEN_KEY = 'matrix_admin_token';

/** Подписанные данные запуска мини-приложения MAX (для проверки на сервере) */
export function getMaxInitData() {
  try {
    return window.WebApp?.initData || '';
  } catch {
    return '';
  }
}

export function getAdminToken() {
  try {
    return sessionStorage.getItem(ADMIN_TOKEN_KEY) || '';
  } catch {
    return '';
  }
}

export function setAdminToken(token) {
  try {
    if (token) sessionStorage.setItem(ADMIN_TOKEN_KEY, token);
    else sessionStorage.removeItem(ADMIN_TOKEN_KEY);
  } catch {
    /* sessionStorage недоступен — токен живёт только до перезагрузки */
  }
}

export function authHeaders() {
  const headers = {};
  const initData = getMaxInitData();
  if (initData) headers['X-Max-Init-Data'] = initData;
  const adminToken = getAdminToken();
  if (adminToken) headers['X-Admin-Token'] = adminToken;
  return headers;
}

export async function apiCall(url, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${url}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(options.headers ?? {})
      }
    });

    if (!response.ok) {
      let errorMessage;
      try {
        const text = await response.text();
        if (!text || !text.trim()) {
          errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        } else {
          const parsed = JSON.parse(text);
          errorMessage = parsed.detail || parsed.message || JSON.stringify(parsed);
        }
      } catch (err) {
        errorMessage = `HTTP ${response.status}: ${response.statusText}`;
      }
      const error = new Error(errorMessage || 'Ошибка запроса');
      // Добавляем статус к ошибке для удобной проверки
      error.status = response.status;
      throw error;
    }

    const contentType = response.headers.get('content-type') ?? '';
    const isJson = contentType.includes('application/json');
    const text = await response.text();

    if (!text || !text.trim()) {
      if (url.includes('/members/') || url.includes('/list') || url.endsWith('/')) {
        return [];
      }
      return null;
    }

    if (isJson || text.trim().startsWith('[') || text.trim().startsWith('{')) {
      try {
        return JSON.parse(text);
      } catch (parseError) {
        console.error('Ошибка парсинга JSON:', text.slice(0, 200));
        if (url.includes('/members/')) {
          console.warn('Возвращаем пустой массив из-за ошибки парсинга');
          return [];
        }
        throw new Error('Невалидный JSON ответ от сервера');
      }
    }

    return text;
  } catch (error) {
    // Не логируем 404 ошибки для проверки участия в соревнованиях - это нормальная ситуация
    const isParticipationCheck = url.includes('/participants/') && error?.status === 404;
    if (!isParticipationCheck) {
      console.error('API Error:', url, error);
    }
    if (url.includes('/members/')) {
      console.warn('Возвращаем пустой массив для участников из-за ошибки');
      return [];
    }
    throw error;
  }
}

export async function apiPost(url, body, options = {}) {
  return apiCall(url, {
    method: 'POST',
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...options
  });
}

export async function apiPut(url, body, options = {}) {
  return apiCall(url, {
    method: 'PUT',
    body: body !== undefined ? JSON.stringify(body) : undefined,
    ...options
  });
}

export async function apiDelete(url, options = {}) {
  return apiCall(url, {
    method: 'DELETE',
    ...options
  });
}

export function getApiBase() {
  return API_BASE;
}

