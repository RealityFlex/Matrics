import React from 'react';
import { Button } from '../../../components/ui/index.jsx';
import { StatIcon } from '../../../components/ui/icons.jsx';

const FREQUENCY_OPTIONS = [
  { value: 'daily', label: 'Ежедневно' },
  { value: 'weekly', label: 'Еженедельно' },
  { value: 'monthly', label: 'Ежемесячно' }
];

export function HabitForm({
  values,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  coinsInfo,
  intelligenceInfo,
  satisfactionInfo
}) {
  return (
    <form className="fc-form" onSubmit={onSubmit}>
      <div className="form-group">
        <label htmlFor="habitName">Название привычки</label>
        <input
          id="habitName"
          type="text"
          placeholder="Например: утренняя зарядка"
          value={values.name}
          onChange={(event) => onChange('name', event.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="form-group">
        <label htmlFor="habitDescription">Описание</label>
        <textarea
          id="habitDescription"
          rows={3}
          placeholder="Подробности"
          value={values.description}
          onChange={(event) => onChange('description', event.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="form-group">
        <label htmlFor="habitFrequency">Частота</label>
        <select
          id="habitFrequency"
          value={values.frequency}
          onChange={(event) => onChange('frequency', event.target.value)}
          disabled={disabled}
        >
          {FREQUENCY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="fc-reward-hints">
        <span className="fc-reward-hints__title">Награда</span>
        <p className="fc-reward-hint">
          <StatIcon kind="coins" />
          <span>{coinsInfo}</span>
        </p>
        <p className="fc-reward-hint">
          <StatIcon kind="intelligence" />
          <span>{intelligenceInfo}</span>
        </p>
        <p className="fc-reward-hint">
          <StatIcon kind="satisfaction" />
          <span>{satisfactionInfo}</span>
        </p>
      </div>

      <Button type="submit" block disabled={disabled}>
        {submitLabel}
      </Button>
    </form>
  );
}

