import React from 'react';
import { Wand2 } from 'lucide-react';
import { Button } from '../../../components/ui/index.jsx';
import { StatIcon } from '../../../components/ui/icons.jsx';

const PRIORITY_OPTIONS = [
  { value: 'low', label: 'Низкий' },
  { value: 'medium', label: 'Средний' },
  { value: 'high', label: 'Высокий' },
  { value: 'urgent', label: 'Срочно' }
];

export function TaskForm({
  values,
  onChange,
  onSubmit,
  submitLabel,
  disabled,
  showGenerate,
  onGenerate,
  isGenerating,
  generateStatus,
  generateDisabled,
  coinsInfo,
  intelligenceInfo
}) {
  return (
    <form className="fc-form" onSubmit={onSubmit}>
      <div className="form-group">
        <label htmlFor="taskTitle">Название задачи</label>
        <input
          id="taskTitle"
          type="text"
          placeholder="Например: выучить новый навык"
          value={values.title}
          onChange={(event) => onChange('title', event.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="form-group">
        <label htmlFor="taskDescription">Описание</label>
        <textarea
          id="taskDescription"
          rows={3}
          placeholder="Подробности задачи"
          value={values.description}
          onChange={(event) => onChange('description', event.target.value)}
          disabled={disabled}
        />
      </div>

      <div className="form-group">
        <label htmlFor="taskPriority">Приоритет</label>
        <select
          id="taskPriority"
          value={values.priority}
          onChange={(event) => onChange('priority', event.target.value)}
          disabled={disabled}
        >
          {PRIORITY_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="fc-reward-hints">
        <span className="fc-reward-hints__title">Награда</span>
        <p className="fc-reward-hint" id="taskCoinsInfo">
          <StatIcon kind="coins" />
          <span>{coinsInfo}</span>
        </p>
        <p className="fc-reward-hint" id="taskIntelligenceInfo">
          <StatIcon kind="intelligence" />
          <span>{intelligenceInfo}</span>
        </p>
      </div>

      <div className="fc-form-actions">
        <Button type="submit" block disabled={disabled}>
          {submitLabel}
        </Button>
        {showGenerate ? (
          <>
            <Button
              variant="secondary"
              block
              icon={<Wand2 size={16} />}
              onClick={onGenerate}
              loading={isGenerating}
              disabled={disabled || generateDisabled}
            >
              {isGenerating ? 'Генерация…' : 'Сгенерировать задачу'}
            </Button>
            {generateStatus ? (
              <p className="fc-form-status" id="generateTaskStatus" role="status">
                {generateStatus}
              </p>
            ) : null}
          </>
        ) : null}
      </div>
    </form>
  );
}
