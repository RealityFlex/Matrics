// Подписи периодичности привычек (значения приходят с бэкенда на английском)
export const FREQUENCY_LABELS = {
  daily: 'Ежедневно',
  weekly: 'Еженедельно',
  monthly: 'Ежемесячно'
};

export function getFrequencyLabel(frequency) {
  const key = (frequency || 'daily').toString().toLowerCase();
  return FREQUENCY_LABELS[key] ?? 'Свой график';
}
