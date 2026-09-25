import React from 'react';

export const TASK_FILTERS = [
  { id: 'all', label: 'Все' },
  { id: 'todo', label: 'К выполнению' },
  { id: 'completed', label: 'Выполнено' }
];

export function TaskFilters({ activeFilter, onChange }) {
  return (
    <div className="filter-tabs" id="tasksFilter">
      {TASK_FILTERS.map((filter) => (
        <button
          key={filter.id}
          type="button"
          className={`filter-tab ${activeFilter === filter.id ? 'active' : ''}`}
          data-status={filter.id}
          onClick={() => onChange(filter.id)}
        >
          {filter.label}
        </button>
      ))}
    </div>
  );
}

