import React from 'react';
import { Award, Brain, CalendarCheck, CalendarDays, Coins, Flame, ListChecks, Repeat } from 'lucide-react';
import { Button } from '../../components/ui/index.jsx';
import { RewardChips } from '../../components/ui/icons.jsx';

/** Награды в ячейке таблицы: чипы «монеты / интеллект», нули скрыты. */
export function RewardsCell({ coins, intelligence }) {
  if (!coins && !intelligence) {
    return <span className="admin-muted">—</span>;
  }
  return <RewardChips rewards={{ coins, intelligence }} signed={false} />;
}

/** Номер призового места вместо медалей-эмодзи. */
export function PlaceBadge({ place, large = false }) {
  return (
    <span className={`admin-place admin-place--${place} ${large ? 'admin-place--lg' : ''}`} aria-label={`${place} место`}>
      {place}
    </span>
  );
}

/** Кнопки «Сохранить / Отмена» в подвале модального окна формы. */
export function ModalFormActions({ formId, isSubmitting, onCancel, submitLabel = 'Сохранить' }) {
  return (
    <div className="admin-modal-actions">
      <Button variant="secondary" onClick={onCancel} disabled={isSubmitting}>
        Отмена
      </Button>
      <Button type="submit" form={formId} loading={isSubmitting}>
        {isSubmitting ? 'Сохранение…' : submitLabel}
      </Button>
    </div>
  );
}

// Тип требования достижения → линейная иконка (эмодзи из поля icon в БД не показываем)
const REQUIREMENT_ICONS = {
  lessons_attended: CalendarCheck,
  attendance_streak: Flame,
  tasks_completed: ListChecks,
  habits_logged: Repeat,
  events_attended: CalendarDays,
  coins_earned: Coins,
  coins: Coins,
  intelligence_points_earned: Brain,
  intelligence_points: Brain
};

export function RequirementIcon({ type, size = 16 }) {
  const Icon = REQUIREMENT_ICONS[type] ?? Award;
  return <Icon size={size} className="icon-primary" aria-hidden="true" />;
}
