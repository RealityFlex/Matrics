const STORAGE_KEY = 'habitActionStatus';

function readStorage() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed === 'object') {
      return parsed;
    }
    return {};
  } catch (error) {
    console.warn('Не удалось прочитать состояние привычек из localStorage', error);
    return {};
  }
}

function writeStorage(map) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(map));
  } catch (error) {
    console.warn('Не удалось сохранить состояние привычек в localStorage', error);
  }
}

function startOfPeriod(date, frequency) {
  const result = new Date(date);
  result.setHours(0, 0, 0, 0);
  const normalizedFrequency = (frequency || 'daily').toLowerCase();
  if (normalizedFrequency === 'weekly') {
    const day = result.getDay();
    const diff = (day + 6) % 7;
    result.setDate(result.getDate() - diff);
  } else if (normalizedFrequency === 'monthly') {
    result.setDate(1);
  }
  return result;
}

export function isSamePeriod(timestamp, frequency) {
  if (!timestamp) {
    return false;
  }
  const lastDate = new Date(timestamp);
  const now = new Date();
  const normalizedLast = startOfPeriod(lastDate, frequency);
  const normalizedNow = startOfPeriod(now, frequency);
  return normalizedLast.getTime() === normalizedNow.getTime();
}

export function getHabitActionStatus(habitId, frequency) {
  const map = readStorage();
  const entry = map[habitId];
  if (!entry) {
    return null;
  }
  const freq = frequency || entry.frequency || 'daily';
  if (!isSamePeriod(entry.timestamp, freq)) {
    delete map[habitId];
    writeStorage(map);
    return null;
  }
  return entry;
}

export function setHabitActionStatus(habitId, action, frequency) {
  const map = readStorage();
  map[habitId] = {
    action,
    timestamp: new Date().toISOString(),
    frequency: frequency || 'daily'
  };
  writeStorage(map);
}

export function clearHabitActionStatus(habitId) {
  const map = readStorage();
  if (map[habitId]) {
    delete map[habitId];
    writeStorage(map);
  }
}

