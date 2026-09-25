import React from 'react';
import { TaskCard } from './TaskCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function TaskList({ tasks, isLoading, error, onComplete, onEdit, onDelete, onRetry }) {
  if (isLoading) {
    return (
      <div className="cards-list" id="tasksList">
        <StateView state="loading" message="Загрузка задач…" compact />
      </div>
    );
  }

  if (error) {
    return (
      <div className="cards-list" id="tasksList">
        <StateView state="error" title="Не удалось загрузить задачи" message={error} onRetry={onRetry} compact />
      </div>
    );
  }

  if (!tasks.length) {
    return (
      <div className="cards-list" id="tasksList">
        <StateView state="empty" title="Задач пока нет" message="Добавьте первую задачу кнопкой «Добавить»." compact />
      </div>
    );
  }

  return (
    <div className="cards-list" id="tasksList">
      {tasks.map((task) => (
        <TaskCard
          key={task.id}
          task={task}
          onComplete={onComplete}
          onEdit={onEdit}
          onDelete={onDelete}
        />
      ))}
    </div>
  );
}
