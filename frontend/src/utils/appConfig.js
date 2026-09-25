import { getAppConfig } from '../services/users.js';

let cached = null;

/** Конфигурация приложения (ник бота) — запрашивается один раз */
export function loadAppConfig() {
  if (!cached) {
    cached = getAppConfig().catch(() => {
      cached = null;
      return { bot_username: null, bot_link: null };
    });
  }
  return cached;
}
