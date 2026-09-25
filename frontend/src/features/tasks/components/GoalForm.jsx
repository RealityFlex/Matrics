import React from 'react';
import { Button } from '../../../components/ui/index.jsx';

export function GoalForm({ values, onChange, onSubmit, submitLabel, disabled }) {
  const handleChange = (field) => (event) => {
    onChange(field, event.target.value);
  };

  return (
    <form className="form-group fc-form" onSubmit={onSubmit}>
      <div>
        <label htmlFor="goalTitle">Название цели</label>
        <input
          id="goalTitle"
          type="text"
          value={values.title}
          onChange={handleChange('title')}
          placeholder="Например, создать учебное приложение"
          required
          maxLength={200}
        />
      </div>

      <div>
        <label htmlFor="goalDescription">Описание</label>
        <textarea
          id="goalDescription"
          value={values.description}
          onChange={handleChange('description')}
          placeholder="Опишите, какого результата хотите добиться"
          rows={4}
          maxLength={2000}
        />
      </div>

      <div>
        <label htmlFor="goalDueDate">Дедлайн (необязательно)</label>
        <input
          id="goalDueDate"
          type="datetime-local"
          value={values.dueDate}
          onChange={handleChange('dueDate')}
        />
      </div>

      <Button type="submit" block loading={disabled}>
        {submitLabel}
      </Button>
    </form>
  );
}

