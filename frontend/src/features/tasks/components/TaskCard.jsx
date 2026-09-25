import React from 'react';
import { Check, Pencil, Trash2 } from 'lucide-react';
import { Badge, Button } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';

export function TaskCard({ task, onComplete, onEdit, onDelete }) {
  const isCompleted = task.status === 'completed';
  const rewards = {
    coins: task.reward_coins ?? 0,
    intelligence: task.reward_intelligence_points ?? 0,
    satisfaction: task.reward_satisfaction ?? 0
  };

  return (
    <div className="card fc-card">
      <div className="fc-card__head">
        <div className="fc-card__title">{task.title}</div>
        <Badge tone={isCompleted ? 'success' : 'neutral'}>{isCompleted ? 'Выполнена' : 'К выполнению'}</Badge>
      </div>
      {task.description ? <div className="fc-card__desc">{task.description}</div> : null}
      <RewardChips rewards={rewards} />
      <div className="fc-actions">
        {!isCompleted ? (
          <Button size="sm" block icon={<Check size={16} />} onClick={() => onComplete(task)}>
            Выполнить
          </Button>
        ) : null}
        <div className="fc-actions__row">
          {!isCompleted ? (
            <Button size="sm" variant="secondary" icon={<Pencil size={16} />} onClick={() => onEdit(task)}>
              Изменить
            </Button>
          ) : null}
          <Button size="sm" variant="secondary" icon={<Trash2 size={16} />} onClick={() => onDelete(task)}>
            Удалить
          </Button>
        </div>
      </div>
    </div>
  );
}
