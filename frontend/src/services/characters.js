import { apiCall, apiPost } from './apiClient.js';

export function getCharacterByUser(userId) {
  return apiCall(`/characters/user/${userId}`);
}

export function getCharacter(characterId) {
  return apiCall(`/characters/${characterId}`);
}

export function createCharacter(payload) {
  return apiPost('/characters/', payload);
}

export function refreshCharacter(userId) {
  return getCharacterByUser(userId);
}


// ---------- Кастомизация персонажа и окружения ----------

export function getAppearanceCatalog(userId) {
  return apiCall(`/characters/appearance/catalog?user_id=${userId}`);
}

export function equipAppearance(userId, setId) {
  return apiPost(`/characters/user/${userId}/appearance/equip?user_id=${userId}`, { set_id: setId });
}

export function purchaseAppearance(userId, setId) {
  return apiPost(`/characters/user/${userId}/appearance/purchase?user_id=${userId}`, { set_id: setId });
}

/** Персонаж пользователя; если его ещё нет (например, у куратора) — создаётся автоматически */
export async function ensureCharacter(userId, name) {
  try {
    return await getCharacterByUser(userId);
  } catch (error) {
    if (error?.status !== 404) throw error;
    await createCharacter({ user_id: userId, name: name || 'Мой персонаж' });
    return getCharacterByUser(userId);
  }
}
