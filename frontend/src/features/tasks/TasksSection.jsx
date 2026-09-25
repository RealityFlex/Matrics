import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import { useRefreshUserAndCharacter } from '../../hooks/useRefreshUserAndCharacter.js';
import {
  completeTask as completeTaskRequest,
  createTask,
  deleteTask as deleteTaskRequest,
  generateTask,
  getGenerateStatus,
  getTask,
  getUserTasks,
  updateTask,
  getUserGoals,
  createGoal,
  updateGoal,
  deleteGoal,
  updateGoalTask,
  completeGoal
} from '../../services/tasks.js';
import { TaskFilters } from './components/TaskFilters.jsx';
import { TaskList } from './components/TaskList.jsx';
import { TaskModal } from './components/TaskModal.jsx';
import { GoalCard } from './components/GoalCard.jsx';
import { GoalModal } from './components/GoalModal.jsx';
import { GoalTaskModal } from './components/GoalTaskModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { toast } from '../../components/ui/toast.jsx';
import { Plus } from 'lucide-react';
import { Button, StateView } from '../../components/ui/index.jsx';
import { RewardChips } from '../../components/ui/icons.jsx';
import '../../styles/features-core.css';

const rewardsOf = (r) => ({
  coins: r.reward_coins ?? 0,
  intelligence: r.reward_intelligence_points ?? 0,
  satisfaction: r.reward_satisfaction ?? 0
});

const DEFAULT_TASK_FORM = {
  title: '',
  description: '',
  priority: 'medium'
};

const DEFAULT_COINS_INFO_CREATE =
  'Монеты начисляются автоматически (0–50) в зависимости от сложности задачи.';
const DEFAULT_INTEL_INFO_CREATE =
  'Очки интеллекта начисляются автоматически (0–15) в зависимости от умственной нагрузки.';

function toLocalInputDate(value) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  const tzOffset = date.getTimezoneOffset();
  const local = new Date(date.getTime() - tzOffset * 60000);
  return local.toISOString().slice(0, 16);
}

export function TasksSection({ isActive }) {
  const { user } = useAppState();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();

  const [tasks, setTasks] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState(DEFAULT_TASK_FORM);
  const [createCoinsInfo, setCreateCoinsInfo] = useState(DEFAULT_COINS_INFO_CREATE);
  const [createIntelInfo, setCreateIntelInfo] = useState(DEFAULT_INTEL_INFO_CREATE);
  const [generateStatus, setGenerateStatus] = useState('');
  const [canGenerate, setCanGenerate] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSavingTask, setIsSavingTask] = useState(false);

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState(DEFAULT_TASK_FORM);
  const [editTaskId, setEditTaskId] = useState(null);
  const [editCoinsInfo, setEditCoinsInfo] = useState('');
  const [editIntelInfo, setEditIntelInfo] = useState('');
  const [isUpdatingTask, setIsUpdatingTask] = useState(false);

  const [goals, setGoals] = useState([]);
  const [goalsLoading, setGoalsLoading] = useState(false);
  const [goalsError, setGoalsError] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, type: null, item: null, onConfirm: null });
  const [expandedGoals, setExpandedGoals] = useState([]);
  const [isGoalModalOpen, setIsGoalModalOpen] = useState(false);
  const [goalForm, setGoalForm] = useState({
    title: '',
    description: '',
    dueDate: ''
  });
  const [isSavingGoal, setIsSavingGoal] = useState(false);
  const [editingGoal, setEditingGoal] = useState(null);
  const [goalFeedback, setGoalFeedback] = useState('');

  const [isGoalTaskModalOpen, setIsGoalTaskModalOpen] = useState(false);
  const [goalTaskForm, setGoalTaskForm] = useState({
    title: '',
    description: '',
    status: 'todo',
    dueDate: ''
  });
  const [editingGoalTask, setEditingGoalTask] = useState(null);
  const [isSavingGoalTask, setIsSavingGoalTask] = useState(false);

  const filteredTasks = useMemo(() => {
    if (filter === 'all') {
      return tasks;
    }
    return tasks.filter((task) => task.status === filter);
  }, [tasks, filter]);

  const loadTasks = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await getUserTasks(user.id);
      setTasks(Array.isArray(data) ? data : []);
    } catch (loadError) {
      console.error('Ошибка загрузки задач:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить задачи');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  const loadGoals = useCallback(async () => {
    if (!user?.id) {
      setGoals([]);
      return;
    }
    setGoalsLoading(true);
    setGoalsError(null);
    try {
      const data = await getUserGoals(user.id);
      setGoals(Array.isArray(data) ? data : []);
    } catch (loadError) {
      console.error('Ошибка загрузки целей:', loadError);
      setGoalsError(loadError.message ?? 'Не удалось загрузить цели');
    } finally {
      setGoalsLoading(false);
    }
  }, [user?.id]);

  const checkGenerateAvailability = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    try {
      const status = await getGenerateStatus(user.id);
      if (!status.can_generate) {
        const lastGenerated = status.last_generated ? new Date(status.last_generated) : null;
        if (lastGenerated) {
          const now = new Date();
          const diffHours = Math.max(0, 24 - Math.floor((now - lastGenerated) / (1000 * 60 * 60)));
          setGenerateStatus(`Генерация доступна через ${diffHours} ч`);
        } else {
          setGenerateStatus('Генерация временно недоступна');
        }
        setCanGenerate(false);
      } else {
        setGenerateStatus('Генерация доступна');
        setCanGenerate(true);
      }
    } catch (statusError) {
      console.warn('Не удалось проверить статус генерации задач:', statusError);
    }
  }, [user?.id]);

  useEffect(() => {
    if (isActive && user?.id) {
      loadTasks();
      loadGoals();
    }
  }, [isActive, user?.id]); // Убрали loadTasks и loadGoals из зависимостей

  const openCreateModal = () => {
    setCreateForm(DEFAULT_TASK_FORM);
    setCreateCoinsInfo(DEFAULT_COINS_INFO_CREATE);
    setCreateIntelInfo(DEFAULT_INTEL_INFO_CREATE);
    setGenerateStatus('');
    setCanGenerate(true);
    setIsCreateModalOpen(true);
    checkGenerateAvailability();
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
  };

  const updateCreateForm = (field, value) => {
    setCreateForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleCreateTask = async (event) => {
    event.preventDefault();
    if (!user?.id || !createForm.title.trim()) {
      return;
    }
    setIsSavingTask(true);
    try {
      await createTask(user.id, {
        title: createForm.title.trim(),
        description: createForm.description.trim(),
        priority: createForm.priority
      });
      closeCreateModal();
      setCreateForm(DEFAULT_TASK_FORM);
      await loadTasks();
    } catch (createError) {
      console.error('Ошибка создания задачи:', createError);
      setGenerateStatus(createError.message ?? 'Не удалось создать задачу');
    } finally {
      setIsSavingTask(false);
    }
  };

  const handleGenerateTask = async () => {
    if (!user?.id || isGenerating) {
      return;
    }
    setIsGenerating(true);
    try {
      const status = await getGenerateStatus(user.id);
      if (!status.can_generate) {
        setGenerateStatus('Вы уже сгенерировали задачу сегодня. Попробуйте завтра!');
        setCanGenerate(false);
        return;
      }

      const generatedTask = await generateTask(user.id);
      setCreateForm({
        title: generatedTask.title ?? '',
        description: generatedTask.description ?? '',
        priority: generatedTask.priority ?? 'medium'
      });
      setCreateCoinsInfo(
        `Предварительно: ${generatedTask.reward_coins} монет (пересчитывается при сохранении)`
      );
      setCreateIntelInfo(
        `Предварительно: ${generatedTask.reward_intelligence_points} очков интеллекта (пересчитывается при сохранении)`
      );
      setGenerateStatus(
        'Задача сгенерирована — проверьте и сохраните её.'
      );
      await checkGenerateAvailability();
    } catch (generateError) {
      console.error('Ошибка генерации задачи:', generateError);
      const message = generateError.message ?? 'Не удалось сгенерировать задачу';
      if (message.includes('429') || message.includes('уже сгенерировали')) {
        setGenerateStatus('Вы уже сгенерировали задачу сегодня. Попробуйте завтра!');
      } else {
        setGenerateStatus(message);
      }
    } finally {
      setIsGenerating(false);
    }
  };

  const openEditModal = async (task) => {
    try {
      const freshTask = await getTask(task.id);
      setEditTaskId(freshTask.id);
      setEditForm({
        title: freshTask.title ?? '',
        description: freshTask.description ?? '',
        priority: freshTask.priority ?? 'medium'
      });
      setEditCoinsInfo(`Сейчас: ${freshTask.reward_coins} монет (пересчитывается автоматически)`);
      setEditIntelInfo(
        `Сейчас: ${freshTask.reward_intelligence_points} очков интеллекта (пересчитывается автоматически)`
      );
      setIsEditModalOpen(true);
    } catch (editError) {
      console.error('Ошибка загрузки задачи:', editError);
      setError(editError.message ?? 'Не удалось загрузить задачу для редактирования');
    }
  };

  const closeEditModal = () => {
    setIsEditModalOpen(false);
    setEditTaskId(null);
  };

  const updateEditForm = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleUpdateTask = async (event) => {
    event.preventDefault();
    if (!editTaskId || !editForm.title.trim()) {
      return;
    }
    setIsUpdatingTask(true);
    try {
      await updateTask(editTaskId, {
        title: editForm.title.trim(),
        description: editForm.description.trim(),
        priority: editForm.priority
      });
      closeEditModal();
      await loadTasks();
    } catch (updateError) {
      console.error('Ошибка обновления задачи:', updateError);
      toast.error('Задача не обновлена', updateError.message ?? 'Попробуйте ещё раз');
    } finally {
      setIsUpdatingTask(false);
    }
  };

  const handleCompleteTask = async (task) => {
    try {
      await completeTaskRequest(task.id);
      toast.reward(
        'Задача выполнена',
        <>
          {task.title}
          <RewardChips rewards={rewardsOf(task)} />
        </>
      );
      await loadTasks();
      await refreshUserAndCharacter();
    } catch (completeError) {
      console.error('Ошибка выполнения задачи:', completeError);
      toast.error('Задача не выполнена', completeError.message ?? 'Попробуйте ещё раз');
      setError(completeError.message ?? 'Не удалось выполнить задачу');
    }
  };

  const handleDeleteTask = async (task) => {
    setDeleteConfirm({
      isOpen: true,
      type: 'task',
      item: task,
      onConfirm: async () => {
        try {
          await deleteTaskRequest(task.id);
          await loadTasks();
        } catch (deleteError) {
          console.error('Ошибка удаления задачи:', deleteError);
          setError(deleteError.message ?? 'Не удалось удалить задачу');
        }
      }
    });
  };

  const handleFilterChange = (newFilter) => {
    setFilter(newFilter);
  };

  const openGoalCreateModal = () => {
    setEditingGoal(null);
    setGoalForm({
      title: '',
      description: '',
      dueDate: ''
    });
    setGoalFeedback('');
    setIsGoalModalOpen(true);
  };

  const openGoalEditModal = (goal) => {
    setEditingGoal(goal);
    setGoalForm({
      title: goal.title ?? '',
      description: goal.description ?? '',
      dueDate: toLocalInputDate(goal.due_date)
    });
    setGoalFeedback('');
    setIsGoalModalOpen(true);
  };

  const closeGoalModal = () => {
    setIsGoalModalOpen(false);
    setEditingGoal(null);
  };

  const updateGoalForm = (field, value) => {
    setGoalForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveGoal = async (event) => {
    event.preventDefault();
    if (!user?.id || !goalForm.title.trim()) {
      return;
    }
    setIsSavingGoal(true);
    setGoalFeedback('');
    try {
      const payload = {
        title: goalForm.title.trim(),
        description: goalForm.description.trim() || null,
        due_date: goalForm.dueDate ? new Date(goalForm.dueDate).toISOString() : null
      };

      if (editingGoal) {
        await updateGoal(editingGoal.id, payload);
      } else {
        const createdGoal = await createGoal(user.id, payload);
        if (createdGoal?.id) {
          setExpandedGoals((prev) => {
            if (prev.includes(createdGoal.id)) {
              return prev;
            }
            return [...prev, createdGoal.id];
          });
        }
      }

      closeGoalModal();
      await loadGoals();
    } catch (goalError) {
      console.error('Ошибка сохранения цели:', goalError);
      setGoalFeedback(goalError.message ?? 'Не удалось сохранить цель');
    } finally {
      setIsSavingGoal(false);
    }
  };

  const handleDeleteGoal = async (goal) => {
    setDeleteConfirm({
      isOpen: true,
      type: 'goal',
      item: goal,
      onConfirm: async () => {
        try {
          await deleteGoal(goal.id);
          setExpandedGoals((prev) => prev.filter((id) => id !== goal.id));
          await loadGoals();
        } catch (goalError) {
          console.error('Ошибка удаления цели:', goalError);
          setGoalsError(goalError.message ?? 'Не удалось удалить цель');
        }
      }
    });
  };

  const toggleGoalExpanded = (goalId) => {
    setExpandedGoals((prev) => {
      if (prev.includes(goalId)) {
        return prev.filter((id) => id !== goalId);
      }
      return [...prev, goalId];
    });
  };

  const handleCompleteGoal = async (goal) => {
    try {
      await completeGoal(goal.id);
      await loadGoals();
      await refreshUserAndCharacter();
    } catch (goalError) {
      console.error('Ошибка завершения цели:', goalError);
      setGoalsError(goalError.message ?? 'Не удалось завершить цель');
    }
  };

  const openGoalTaskModal = (goal, task) => {
    setEditingGoalTask({ goalId: goal.id, taskId: task.id });
    setGoalTaskForm({
      title: task.title ?? '',
      description: task.description ?? '',
      status: task.status ?? 'todo',
      dueDate: toLocalInputDate(task.due_date)
    });
    setGoalFeedback('');
    setIsGoalTaskModalOpen(true);
  };

  const closeGoalTaskModal = () => {
    setIsGoalTaskModalOpen(false);
    setEditingGoalTask(null);
  };

  const updateGoalTaskForm = (field, value) => {
    setGoalTaskForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSaveGoalTask = async (event) => {
    event.preventDefault();
    if (!editingGoalTask || !goalTaskForm.title.trim()) {
      return;
    }
    setIsSavingGoalTask(true);
    setGoalFeedback('');
    try {
      const payload = {
        title: goalTaskForm.title.trim(),
        description: goalTaskForm.description.trim() || null,
        status: goalTaskForm.status,
        due_date: goalTaskForm.dueDate ? new Date(goalTaskForm.dueDate).toISOString() : null
      };
      const response = await updateGoalTask(
        editingGoalTask.goalId,
        editingGoalTask.taskId,
        payload
      );
      if (response?.rewards) {
        await refreshUserAndCharacter();
      }
      closeGoalTaskModal();
      await loadGoals();
    } catch (goalError) {
      console.error('Ошибка обновления подзадачи:', goalError);
      setGoalFeedback(goalError.message ?? 'Не удалось обновить подзадачу');
    } finally {
      setIsSavingGoalTask(false);
    }
  };

  const handleCompleteGoalTask = async (goal, task) => {
    try {
      const response = await updateGoalTask(goal.id, task.id, { status: 'completed' });
      if (response?.rewards) {
        await refreshUserAndCharacter();
      }
      await loadGoals();
    } catch (goalError) {
      console.error('Ошибка завершения подзадачи:', goalError);
      setGoalsError(goalError.message ?? 'Не удалось завершить подзадачу');
    }
  };

  return (
    <div>
      <div className="section-header fc-section-header">
        <h2>Цели</h2>
        <Button size="sm" variant="secondary" icon={<Plus size={16} />} onClick={openGoalCreateModal} aria-label="Добавить цель">
          Добавить
        </Button>
      </div>

      {goalFeedback ? <div className="inline-error" role="alert">{goalFeedback}</div> : null}

      <div className="cards-list" id="goalsList">
        {goalsLoading ? (
          <StateView state="loading" message="Загрузка целей…" compact />
        ) : goalsError ? (
          <StateView state="error" title="Не удалось загрузить цели" message={goalsError} onRetry={loadGoals} compact />
        ) : goals.length === 0 ? (
          <StateView state="empty" title="Целей пока нет" message="Большая цель разбивается на подзадачи с наградой за каждую." compact />
        ) : (
          goals.map((goal) => (
            <GoalCard
              key={goal.id}
              goal={goal}
              isExpanded={expandedGoals.includes(goal.id)}
              onToggleExpand={toggleGoalExpanded}
              onEditGoal={openGoalEditModal}
              onDeleteGoal={handleDeleteGoal}
              onCompleteGoal={handleCompleteGoal}
              onEditGoalTask={openGoalTaskModal}
              onCompleteGoalTask={handleCompleteGoalTask}
            />
          ))
        )}
      </div>

      <div className="section-header fc-section-header">
        <h2>Задачи</h2>
        <Button size="sm" variant="secondary" icon={<Plus size={16} />} id="addTaskBtn" onClick={openCreateModal} aria-label="Добавить задачу">
          Добавить
        </Button>
      </div>

      <TaskFilters activeFilter={filter} onChange={handleFilterChange} />

      <TaskList
        tasks={filteredTasks}
        isLoading={isLoading}
        error={error}
        onComplete={handleCompleteTask}
        onEdit={openEditModal}
        onDelete={handleDeleteTask}
        onRetry={loadTasks}
      />

      <TaskModal
        title="Новая задача"
        isOpen={isCreateModalOpen}
        onClose={closeCreateModal}
        values={createForm}
        onChange={updateCreateForm}
        onSubmit={handleCreateTask}
        submitLabel="Создать задачу"
        disabled={isSavingTask}
        showGenerate
        onGenerate={handleGenerateTask}
        isGenerating={isGenerating}
        generateStatus={generateStatus}
        generateDisabled={!canGenerate}
        coinsInfo={createCoinsInfo}
        intelligenceInfo={createIntelInfo}
      />

      <TaskModal
        title="Редактировать задачу"
        isOpen={isEditModalOpen}
        onClose={closeEditModal}
        values={editForm}
        onChange={updateEditForm}
        onSubmit={handleUpdateTask}
        submitLabel="Обновить задачу"
        disabled={isUpdatingTask}
        showGenerate={false}
        onGenerate={() => {}}
        isGenerating={false}
        generateStatus=""
        generateDisabled
        coinsInfo={editCoinsInfo || 'Монеты пересчитываются автоматически'}
        intelligenceInfo={editIntelInfo || 'Очки интеллекта пересчитываются автоматически'}
      />

      <GoalModal
        title={editingGoal ? 'Редактировать цель' : 'Новая цель'}
        isOpen={isGoalModalOpen}
        onClose={closeGoalModal}
        values={goalForm}
        onChange={updateGoalForm}
        onSubmit={handleSaveGoal}
        submitLabel={editingGoal ? 'Обновить цель' : 'Создать цель'}
        disabled={isSavingGoal}
      />

      <GoalTaskModal
        title="Редактировать подзадачу"
        isOpen={isGoalTaskModalOpen}
        onClose={closeGoalTaskModal}
        values={goalTaskForm}
        onChange={updateGoalTaskForm}
        onSubmit={handleSaveGoalTask}
        submitLabel="Сохранить изменения"
        disabled={isSavingGoalTask}
      />
      <ConfirmModal
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ ...deleteConfirm, isOpen: false })}
        onConfirm={() => {
          if (deleteConfirm.onConfirm) {
            deleteConfirm.onConfirm();
          }
          setDeleteConfirm({ ...deleteConfirm, isOpen: false });
        }}
        title={deleteConfirm.type === 'task' ? 'Удаление задачи' : 'Удаление цели'}
        message={deleteConfirm.type === 'task' 
          ? 'Удалить задачу?' 
          : 'Удалить цель и все связанные подзадачи?'}
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />
    </div>
  );
}

