import React from 'react';
import { Check, Pencil, SkipForward, Trash2 } from 'lucide-react';
import { Badge, Button } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';
import { getFrequencyLabel } from '../frequency.js';

function getStatusNote(completeDisabled, skipDisabled) {
  if (completeDisabled && skipDisabled) {
    return 'Отметки недоступны до следующего периода';
  }
  if (completeDisabled) {
    return 'Уже выполнено в этом периоде';
  }
  if (skipDisabled) {
    return 'Пропуск уже отмечен в этом периоде';
  }
  return null;
}

export function HabitCard({
  habit,
  frequencyLabel,
  completeDisabled,
  skipDisabled,
  onComplete,
  onSkip,
  onEdit,
  onDelete
}) {
  const completedTooltip = completeDisabled ? 'Уже отмечено. Попробуйте позже' : 'Отметить как выполненную';
  const skippedTooltip = skipDisabled ? 'Уже отмечено. Попробуйте позже' : 'Отметить как пропущенную';
  const label = frequencyLabel || getFrequencyLabel(habit.frequency);
  const statusNote = getStatusNote(completeDisabled, skipDisabled);
  const rewards = {
    coins: habit.reward_coins ?? 0,
    intelligence: habit.reward_intelligence_points ?? 0,
    satisfaction: habit.reward_satisfaction ?? 0
  };

  return (
    <div className="card fc-card">
      <div className="fc-card__head">
        <div className="fc-card__titles">
          <div className="fc-card__title">{habit.name}</div>
          {habit.description ? <div className="fc-card__desc">{habit.description}</div> : null}
        </div>
        <Badge tone="neutral">{label}</Badge>
      </div>
      <RewardChips rewards={rewards} />
      {statusNote ? <p className="fc-muted">{statusNote}</p> : null}
      <div className="fc-actions">
        <div className="fc-actions__row">
          <Button
            size="sm"
            variant="secondary"
            icon={<SkipForward size={16} />}
            onClick={() => onSkip(habit)}
            disabled={skipDisabled}
            title={skippedTooltip}
          >
            Пропустить
          </Button>
          <Button
            size="sm"
            icon={<Check size={16} />}
            onClick={() => onComplete(habit)}
            disabled={completeDisabled}
            title={completedTooltip}
          >
            Выполнить
          </Button>
        </div>
        <div className="fc-actions__row">
          <Button size="sm" variant="ghost" icon={<Pencil size={16} />} onClick={() => onEdit(habit)}>
            Изменить
          </Button>
          <Button size="sm" variant="ghost" icon={<Trash2 size={16} />} onClick={() => onDelete(habit)}>
            Удалить
          </Button>
        </div>
      </div>
    </div>
  );
}
