import React from 'react';
import { CalendarClock, Check, CheckCircle2, ChevronDown, ChevronUp, Flag, Pencil, Trash2 } from 'lucide-react';
import { Badge, Button, ProgressBar } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';

const GOAL_STATUS_INFO = {
  planned: { label: 'Запланирована', tone: 'neutral' },
  in_progress: { label: 'В процессе', tone: 'info' },
  completed: { label: 'Завершена', tone: 'success' },
  cancelled: { label: 'Отменена', tone: 'danger' }
};

const TASK_STATUS_INFO = {
  todo: { label: 'К выполнению', tone: 'neutral' },
  in_progress: { label: 'В процессе', tone: 'info' },
  completed: { label: 'Выполнена', tone: 'success' },
  cancelled: { label: 'Отменена', tone: 'danger' }
};

const UNKNOWN_STATUS = { label: 'Без статуса', tone: 'neutral' };

function formatDate(value) {
  if (!value) {
    return null;
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return null;
  }
  return date.toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

function toRewards(source) {
  return {
    coins: source.reward_coins ?? 0,
    intelligence: source.reward_intelligence_points ?? 0,
    satisfaction: source.reward_satisfaction ?? 0
  };
}

export function GoalCard({
  goal,
  isExpanded,
  onToggleExpand,
  onEditGoal,
  onDeleteGoal,
  onCompleteGoal,
  onEditGoalTask,
  onCompleteGoalTask
}) {
  const totalTasks = goal.tasks?.length ?? 0;
  const completedTasks = goal.tasks?.filter((task) => task.status === 'completed').length ?? 0;
  const allCompleted = totalTasks > 0 && totalTasks === completedTasks;
  const statusInfo = GOAL_STATUS_INFO[goal.status] ?? (goal.status ? UNKNOWN_STATUS : GOAL_STATUS_INFO.planned);
  const isGoalCompleted = goal.status === 'completed';

  const dueDateText = formatDate(goal.due_date);
  const completedAtText = formatDate(goal.completed_at);

  return (
    <div className="card fc-card">
      <div className="fc-card__head">
        <div className="fc-card__titles">
          <div className="fc-card__title">{goal.title}</div>
          {goal.description ? <div className="fc-card__desc">{goal.description}</div> : null}
        </div>
        <Badge tone={statusInfo.tone}>{statusInfo.label}</Badge>
      </div>

      <ProgressBar
        value={completedTasks}
        max={totalTasks}
        label="Подзадачи"
        showValue
        tone={allCompleted ? 'success' : 'primary'}
      />

      <RewardChips rewards={toRewards(goal)} />

      {dueDateText || completedAtText ? (
        <div className="fc-meta">
          {dueDateText ? (
            <span className="fc-chip">
              <CalendarClock size={14} aria-hidden="true" /> Дедлайн: {dueDateText}
            </span>
          ) : null}
          {completedAtText ? (
            <span className="fc-chip">
              <CheckCircle2 size={14} aria-hidden="true" /> Завершена: {completedAtText}
            </span>
          ) : null}
        </div>
      ) : null}

      <div className="fc-actions">
        {!isGoalCompleted && allCompleted ? (
          <Button size="sm" block icon={<Flag size={16} />} onClick={() => onCompleteGoal(goal)}>
            Завершить цель
          </Button>
        ) : null}
        <Button
          size="sm"
          variant="ghost"
          block
          icon={isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          onClick={() => onToggleExpand(goal.id)}
          aria-expanded={isExpanded}
        >
          {isExpanded ? 'Скрыть подзадачи' : `Подзадачи (${totalTasks})`}
        </Button>
        <div className="fc-actions__row">
          {!isGoalCompleted ? (
            <Button size="sm" variant="secondary" icon={<Pencil size={16} />} onClick={() => onEditGoal(goal)}>
              Изменить
            </Button>
          ) : null}
          <Button size="sm" variant="secondary" icon={<Trash2 size={16} />} onClick={() => onDeleteGoal(goal)}>
            Удалить
          </Button>
        </div>
      </div>

      {isExpanded ? (
        <div className="fc-subtasks">
          {goal.tasks && goal.tasks.length > 0 ? (
            goal.tasks.map((task) => {
              const taskInfo = TASK_STATUS_INFO[task.status] ?? (task.status ? UNKNOWN_STATUS : TASK_STATUS_INFO.todo);
              const taskDueDate = formatDate(task.due_date);
              const taskCompletedAt = formatDate(task.completed_at);
              const isTaskCompleted = task.status === 'completed';

              return (
                <div key={task.id} className="fc-subtask">
                  <div className="fc-card__head">
                    <div className="fc-subtask__title">{task.title}</div>
                    <Badge tone={taskInfo.tone}>{taskInfo.label}</Badge>
                  </div>
                  {task.description ? <div className="fc-card__desc">{task.description}</div> : null}
                  <RewardChips rewards={toRewards(task)} />
                  {taskDueDate || taskCompletedAt ? (
                    <div className="fc-meta">
                      {taskDueDate ? (
                        <span className="fc-chip">
                          <CalendarClock size={14} aria-hidden="true" /> {taskDueDate}
                        </span>
                      ) : null}
                      {taskCompletedAt ? (
                        <span className="fc-chip">
                          <CheckCircle2 size={14} aria-hidden="true" /> {taskCompletedAt}
                        </span>
                      ) : null}
                    </div>
                  ) : null}
                  {!isGoalCompleted ? (
                    <div className="fc-actions">
                      <div className="fc-actions__row">
                        {!isTaskCompleted ? (
                          <Button size="sm" icon={<Check size={16} />} onClick={() => onCompleteGoalTask(goal, task)}>
                            Выполнить
                          </Button>
                        ) : null}
                        <Button
                          size="sm"
                          variant="secondary"
                          icon={<Pencil size={16} />}
                          onClick={() => onEditGoalTask(goal, task)}
                        >
                          Изменить
                        </Button>
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })
          ) : (
            <p className="fc-muted">Подзадач пока нет</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
