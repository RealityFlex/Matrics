import React from 'react';
import { Button } from '../../../components/ui/index.jsx';
import { Modal } from '../../../components/common/Modal.jsx';

const STATUS_OPTIONS = [
  { value: 'todo', label: 'К выполнению' },
  { value: 'in_progress', label: 'В процессе' },
  { value: 'completed', label: 'Выполнена' },
  { value: 'cancelled', label: 'Отменена' }
];

export function GoalTaskModal({
  title,
  isOpen,
  onClose,
  values,
  onChange,
  onSubmit,
  submitLabel,
  disabled
}) {
  const handleChange = (field) => (event) => {
    onChange(field, event.target.value);
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title}>
      <form className="form-group fc-form" onSubmit={onSubmit}>
        <div>
          <label htmlFor="goalTaskTitle">Название подзадачи</label>
          <input
            id="goalTaskTitle"
            type="text"
            value={values.title}
            onChange={handleChange('title')}
            required
            maxLength={200}
          />
        </div>

        <div>
          <label htmlFor="goalTaskDescription">Описание</label>
          <textarea
            id="goalTaskDescription"
            value={values.description}
            onChange={handleChange('description')}
            rows={4}
            maxLength={2000}
          />
        </div>

        <div>
          <label htmlFor="goalTaskStatus">Статус</label>
          <select
            id="goalTaskStatus"
            value={values.status}
            onChange={handleChange('status')}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="goalTaskDueDate">Дедлайн (необязательно)</label>
          <input
            id="goalTaskDueDate"
            type="datetime-local"
            value={values.dueDate}
            onChange={handleChange('dueDate')}
          />
        </div>

        <Button type="submit" block loading={disabled}>
          {submitLabel}
        </Button>
      </form>
    </Modal>
  );
}

