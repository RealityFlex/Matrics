import React from 'react';
import { HabitCard } from './HabitCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';
import { getFrequencyLabel } from '../frequency.js';

export function HabitList({
  habits,
  isLoading,
  error,
  onRetry,
  habitStates,
  onComplete,
  onSkip,
  onEdit,
  onDelete
}) {
  if (isLoading) {
    return (
      <div className="cards-list" id="habitsList">
        <StateView state="loading" message="Загрузка привычек…" compact />
      </div>
    );
  }

  if (error && !habits.length) {
    return (
      <div className="cards-list" id="habitsList">
        <StateView state="error" title="Не удалось загрузить привычки" message={error} onRetry={onRetry} compact />
      </div>
    );
  }

  if (!habits.length) {
    return (
      <div className="cards-list" id="habitsList">
        <StateView state="empty" title="Привычек пока нет" message="Добавьте привычку и отмечайте её выполнение." compact />
      </div>
    );
  }

  return (
    <div className="cards-list" id="habitsList">
      {habits.map((habit) => {
        const state = habitStates.get(habit.id) ?? {
          frequencyLabel: getFrequencyLabel(habit.frequency),
          completeDisabled: false,
          skipDisabled: false
        };
        return (
          <HabitCard
            key={habit.id}
            habit={habit}
            frequencyLabel={state.frequencyLabel}
            completeDisabled={state.completeDisabled}
            skipDisabled={state.skipDisabled}
            onComplete={onComplete}
            onSkip={onSkip}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        );
      })}
    </div>
  );
}
