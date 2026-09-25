/**
 * Русские подписи для значений-перечислений бэкенда в админке.
 * Неизвестное значение не показываем «как есть» — возвращаем нейтральный fallback.
 */

export const ROLE_LABELS = {
  student: 'Студент',
  curator: 'Куратор',
  admin: 'Администратор',
  teacher: 'Преподаватель'
};

export const TASK_STATUS_LABELS = {
  todo: 'К выполнению',
  in_progress: 'В процессе',
  completed: 'Выполнена',
  cancelled: 'Отменена'
};

export const GOAL_STATUS_LABELS = {
  planned: 'Запланирована',
  in_progress: 'В процессе',
  completed: 'Достигнута',
  cancelled: 'Отменена'
};

export const TASK_PRIORITY_LABELS = {
  low: 'Низкий',
  medium: 'Средний',
  high: 'Высокий',
  urgent: 'Срочный'
};

export const HABIT_FREQUENCY_LABELS = {
  daily: 'Ежедневно',
  weekly: 'Еженедельно',
  monthly: 'Ежемесячно'
};

export const RARITY_LABELS = {
  common: 'Обычный',
  uncommon: 'Необычный',
  rare: 'Редкий',
  epic: 'Эпический',
  legendary: 'Легендарный'
};

export const ITEM_TYPE_LABELS = {
  consumable: 'Расходуемый',
  equipment: 'Экипировка',
  decoration: 'Декорация',
  special: 'Особый',
  // устаревшие значения из ранних версий формы
  weapon: 'Оружие',
  armor: 'Броня',
  accessory: 'Аксессуар'
};

export const REQUIREMENT_TYPE_LABELS = {
  lessons_attended: 'Посещено занятий',
  attendance_streak: 'Серия посещений подряд',
  tasks_completed: 'Задач выполнено',
  habits_logged: 'Привычки повторены',
  events_attended: 'Событий посещено',
  coins_earned: 'Монет заработано',
  coins: 'Монет на счету',
  intelligence_points_earned: 'Очков интеллекта заработано',
  intelligence_points: 'Очков интеллекта'
};

export const COMPETITION_METRIC_LABELS = {
  tasks_completed: 'Выполненных задач',
  habits_completed: 'Записей в дневнике',
  coins_balance: 'Монет',
  intelligence_points: 'Очков интеллекта'
};

export function labelFor(map, value, fallback = 'Другое') {
  if (value === null || value === undefined || value === '') return '—';
  return map[value] ?? fallback;
}
