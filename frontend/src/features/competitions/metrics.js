// Метрики соревнований и челленджей → понятные подписи (сырые значения из API пользователю не показываем)
export const METRIC_LABELS = {
  tasks_completed: 'Выполненные задачи',
  habits_completed: 'Отмеченные привычки',
  coins_balance: 'Монеты на счету',
  intelligence_points: 'Очки интеллекта',
  lessons_attended: 'Посещённые занятия',
  events_attended: 'Посещённые события'
};

export function metricLabel(type) {
  if (!type) return 'Очки';
  return METRIC_LABELS[type] ?? 'Показатель';
}

export const CHALLENGE_STATUS = {
  pending: { label: 'Ожидает ответа', tone: 'warning' },
  accepted: { label: 'Идёт', tone: 'info' },
  active: { label: 'Идёт', tone: 'info' },
  in_progress: { label: 'Идёт', tone: 'info' },
  declined: { label: 'Отклонён', tone: 'danger' },
  completed: { label: 'Завершён', tone: 'success' },
  finished: { label: 'Завершён', tone: 'success' },
  cancelled: { label: 'Отменён', tone: 'neutral' },
  expired: { label: 'Истёк', tone: 'neutral' }
};

export function challengeStatus(status) {
  return CHALLENGE_STATUS[status?.toLowerCase?.()] ?? { label: 'Неизвестно', tone: 'neutral' };
}
