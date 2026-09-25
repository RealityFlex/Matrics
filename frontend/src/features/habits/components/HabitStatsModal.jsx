import React from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function HabitStatsModal({ isOpen, onClose, stats }) {
  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Статистика привычки">
      {stats ? (
        <div className="stats-grid">
          <div className="stat-card">
            <div className="stat-card-value">{stats.current_streak ?? 0}</div>
            <div className="stat-card-label">Текущая серия</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-value">{stats.longest_streak ?? 0}</div>
            <div className="stat-card-label">Самая длинная серия</div>
          </div>
          <div className="stat-card">
            <div className="stat-card-value">{stats.total_completions ?? 0}</div>
            <div className="stat-card-label">Всего выполнено</div>
          </div>
        </div>
      ) : (
        <StateView state="loading" message="Загрузка статистики…" compact />
      )}
    </Modal>
  );
}

