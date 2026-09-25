import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import { useRefreshUserAndCharacter } from '../../hooks/useRefreshUserAndCharacter.js';
import {
  completeHabit as completeHabitRequest,
  createHabit,
  deleteHabit as deleteHabitRequest,
  getHabit,
  getHabits,
  skipHabit,
  updateHabit
} from '../../services/habits.js';
import { HabitList } from './components/HabitList.jsx';
import { HabitModal } from './components/HabitModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { toast } from '../../components/ui/toast.jsx';
import { Plus } from 'lucide-react';
import { Button } from '../../components/ui/index.jsx';
import { RewardChips } from '../../components/ui/icons.jsx';
import { getFrequencyLabel } from './frequency.js';
import '../../styles/features-core.css';

const rewardsOf = (r) => ({
  coins: r.reward_coins ?? 0,
  intelligence: r.reward_intelligence_points ?? 0,
  satisfaction: r.reward_satisfaction ?? 0
});
import {
  clearHabitActionStatus,
  getHabitActionStatus,
  isSamePeriod,
  setHabitActionStatus
} from '../../utils/habitStatusStorage.js';

const DEFAULT_HABIT_FORM = {
  name: '',
  description: '',
  frequency: 'daily'
};

const DEFAULT_COINS_INFO_CREATE =
  'Монеты начисляются автоматически (2–12) исходя из пользы и регулярности привычки.';
const DEFAULT_INTEL_INFO_CREATE =
  'Очки интеллекта начисляются автоматически (0–5) в зависимости от полезности привычки.';
const DEFAULT_SATISFACTION_INFO_CREATE =
  'Настроение растёт автоматически (2–8) с учётом пользы и регулярности привычки.';
const DEFAULT_COINS_INFO_EDIT = 'Монеты пересчитываются автоматически (2–12).';
const DEFAULT_INTEL_INFO_EDIT = 'Очки интеллекта пересчитываются автоматически (0–5) при изменении привычки.';
const DEFAULT_SATISFACTION_INFO_EDIT =
  'Настроение пересчитывается автоматически (2–8) при изменении привычки.';

function parseDate(value) {
  return value ? new Date(value) : null;
}

function computeHabitState(habit) {
  const frequency = (habit.frequency || 'daily').toLowerCase();
  const frequencyLabel = getFrequencyLabel(frequency);

  const lastCompleted =
    parseDate(habit.last_completed_at) ||
    parseDate(habit.lastCompleted) ||
    parseDate(habit.status?.last_completed_at) ||
    parseDate(habit.status?.lastCompleted);

  const lastSkipped =
    parseDate(habit.last_skipped_at) ||
    parseDate(habit.lastSkipped) ||
    parseDate(habit.status?.last_skipped_at) ||
    parseDate(habit.status?.lastSkipped);

  let completeDisabled = lastCompleted ? isSamePeriod(lastCompleted, frequency) : false;
  let skipDisabled = lastSkipped ? isSamePeriod(lastSkipped, frequency) : false;

  const localStatus = getHabitActionStatus(habit.id, frequency);
  if (localStatus) {
    if (localStatus.action === 'complete') {
      completeDisabled = true;
      skipDisabled = false;
    } else if (localStatus.action === 'skip') {
      skipDisabled = true;
      completeDisabled = false;
    } else if (localStatus.action === 'locked') {
      skipDisabled = true;
      completeDisabled = true;
    }
  }

  return {
    frequency,
    frequencyLabel,
    completeDisabled,
    skipDisabled
  };
}

export function HabitsSection({ isActive }) {
  const { user } = useAppState();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();

  const [habits, setHabits] = useState([]);
  const [habitStates, setHabitStates] = useState(() => new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [createForm, setCreateForm] = useState(DEFAULT_HABIT_FORM);
  const [createCoinsInfo, setCreateCoinsInfo] = useState(DEFAULT_COINS_INFO_CREATE);
  const [createIntelInfo, setCreateIntelInfo] = useState(DEFAULT_INTEL_INFO_CREATE);
  const [createSatisfactionInfo, setCreateSatisfactionInfo] = useState(DEFAULT_SATISFACTION_INFO_CREATE);
  const [isSavingHabit, setIsSavingHabit] = useState(false);

  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [editForm, setEditForm] = useState(DEFAULT_HABIT_FORM);
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, habit: null });
  const [editCoinsInfo, setEditCoinsInfo] = useState(DEFAULT_COINS_INFO_EDIT);
  const [editIntelInfo, setEditIntelInfo] = useState(DEFAULT_INTEL_INFO_EDIT);
  const [editSatisfactionInfo, setEditSatisfactionInfo] = useState(DEFAULT_SATISFACTION_INFO_EDIT);
  const [isUpdatingHabit, setIsUpdatingHabit] = useState(false);
  const [editingHabitId, setEditingHabitId] = useState(null);

  const habitStateMap = useMemo(() => habitStates, [habitStates]);

  const loadHabits = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const list = await getHabits(user.id);
      setHabits(Array.isArray(list) ? list : []);
      const map = new Map();
      (list || []).forEach((habit) => {
        map.set(habit.id, computeHabitState(habit));
      });
      setHabitStates(map);
    } catch (loadError) {
      console.error('Ошибка загрузки привычек:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить привычки');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (isActive && user?.id) {
      loadHabits();
    }
  }, [isActive, user?.id]); // Убрали loadHabits из зависимостей

  const openCreateModal = () => {
    setCreateForm(DEFAULT_HABIT_FORM);
    setCreateCoinsInfo(DEFAULT_COINS_INFO_CREATE);
    setCreateIntelInfo(DEFAULT_INTEL_INFO_CREATE);
    setCreateSatisfactionInfo(DEFAULT_SATISFACTION_INFO_CREATE);
    setIsCreateModalOpen(true);
  };

  const closeCreateModal = () => {
    setIsCreateModalOpen(false);
  };

  const updateCreateForm = (field, value) => {
    setCreateForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleCreateHabit = async (event) => {
    event.preventDefault();
    if (!user?.id || !createForm.name.trim()) {
      return;
    }
    setIsSavingHabit(true);
    try {
      await createHabit(user.id, {
        name: createForm.name.trim(),
        description: createForm.description.trim(),
        frequency: createForm.frequency
      });
      closeCreateModal();
      await loadHabits();
    } catch (createError) {
      console.error('Ошибка создания привычки:', createError);
      const message = createError.message ?? 'Не удалось создать привычку';
      if (message.toLowerCase().includes('не является полезной')) {
        toast.error('Привычка отклонена', 'Система считает её неполезной. Измените описание.');
        setCreateCoinsInfo('Привычка отклонена: система считает её неполезной. Измените описание.');
        setCreateIntelInfo('Сформулируйте привычку с фокусом на здоровье или развитии.');
        setCreateSatisfactionInfo('Настроение не начисляется за непродуктивные привычки.');
      } else {
        toast.error('Привычка не создана', message);
        setCreateCoinsInfo(DEFAULT_COINS_INFO_CREATE);
        setCreateIntelInfo(DEFAULT_INTEL_INFO_CREATE);
        setCreateSatisfactionInfo(DEFAULT_SATISFACTION_INFO_CREATE);
      }
    } finally {
      setIsSavingHabit(false);
    }
  };

  const openEditModal = async (habit) => {
    try {
      const freshHabit = await getHabit(habit.id);
      setEditingHabitId(freshHabit.id);
      setEditForm({
        name: freshHabit.name ?? '',
        description: freshHabit.description ?? '',
        frequency: freshHabit.frequency ?? 'daily'
      });
      setEditCoinsInfo(`Сейчас: ${freshHabit.reward_coins} монет (пересчитывается автоматически)`);
      setEditIntelInfo(
        `Сейчас: ${freshHabit.reward_intelligence_points} очков интеллекта (пересчитывается автоматически)`
      );
      setEditSatisfactionInfo(
        `Сейчас: +${freshHabit.reward_satisfaction} к настроению (пересчитывается автоматически)`
      );
      setIsEditModalOpen(true);
    } catch (editError) {
      console.error('Ошибка загрузки привычки:', editError);
      toast.error('Не удалось открыть привычку', editError.message ?? 'Попробуйте ещё раз');
    }
  };

  const closeEditModal = () => {
    setIsEditModalOpen(false);
    setEditingHabitId(null);
    setEditCoinsInfo(DEFAULT_COINS_INFO_EDIT);
    setEditIntelInfo(DEFAULT_INTEL_INFO_EDIT);
    setEditSatisfactionInfo(DEFAULT_SATISFACTION_INFO_EDIT);
  };

  const updateEditForm = (field, value) => {
    setEditForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleUpdateHabit = async (event) => {
    event.preventDefault();
    if (!editingHabitId || !editForm.name.trim()) {
      return;
    }
    setIsUpdatingHabit(true);
    try {
      await updateHabit(editingHabitId, {
        name: editForm.name.trim(),
        description: editForm.description.trim(),
        frequency: editForm.frequency
      });
      closeEditModal();
      await loadHabits();
    } catch (updateError) {
      console.error('Ошибка обновления привычки:', updateError);
      const message = updateError.message ?? 'Не удалось обновить привычку';
      if (message.toLowerCase().includes('не является полезной')) {
        toast.error('Привычка отклонена', 'Измените её так, чтобы она приносила явную пользу.');
        setEditCoinsInfo('Измените привычку так, чтобы она приносила явную пользу.');
        setEditIntelInfo('Для получения очков привычка должна укреплять здоровье или развивать навыки.');
        setEditSatisfactionInfo('Измените привычку, чтобы она влияла на настроение.');
      } else {
        toast.error('Привычка не обновлена', message);
        setEditCoinsInfo(DEFAULT_COINS_INFO_EDIT);
        setEditIntelInfo(DEFAULT_INTEL_INFO_EDIT);
        setEditSatisfactionInfo(DEFAULT_SATISFACTION_INFO_EDIT);
      }
    } finally {
      setIsUpdatingHabit(false);
    }
  };

  const handleCompleteHabit = async (habit) => {
    try {
      await completeHabitRequest(habit.id);
      const state = habitStateMap.get(habit.id);
      const frequency = state?.frequency || habit.frequency || 'daily';
      setHabitActionStatus(habit.id, 'complete', frequency);
      toast.reward(
        'Привычка отмечена',
        <>
          {habit.name}
          <RewardChips rewards={rewardsOf(habit)} />
        </>
      );
      await loadHabits();
      await refreshUserAndCharacter();
    } catch (completeError) {
      console.error('Ошибка выполнения привычки:', completeError);
      toast.error('Не удалось отметить привычку', completeError.message);
      setError(completeError.message ?? 'Не удалось выполнить привычку');
    }
  };

  const handleSkipHabit = async (habit) => {
    try {
      const result = await skipHabit(habit.id);
      const state = habitStateMap.get(habit.id);
      const frequency = state?.frequency || habit.frequency || 'daily';
      if (result?.status === 'insufficient_resources') {
        console.info('Недостаточно ресурсов для отмены привычки, изменения состояния не выполнены');
        toast.info('Пропуск не отмечен', 'Недостаточно ресурсов для отметки пропуска');
        return;
      }
      setHabitActionStatus(habit.id, 'skip', frequency);
      await loadHabits();
    } catch (skipError) {
      console.error('Ошибка отметки пропуска привычки:', skipError);
      const state = habitStateMap.get(habit.id);
      const frequency = state?.frequency || habit.frequency || 'daily';
      const message = (skipError?.message || '').toLowerCase();
      if (skipError?.status === 400 || message.includes('недостаточно')) {
        setHabitActionStatus(habit.id, 'locked', frequency);
        toast.info('Пропуск не отмечен', 'Недостаточно ресурсов для отметки пропуска');
      } else {
        toast.error('Не удалось отметить пропуск', skipError.message ?? 'Попробуйте ещё раз');
      }
    }
  };

  const handleDeleteHabit = async (habit) => {
    setDeleteConfirm({ isOpen: true, habit });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.habit) return;
    try {
      await deleteHabitRequest(deleteConfirm.habit.id);
      clearHabitActionStatus(deleteConfirm.habit.id);
      await loadHabits();
    } catch (deleteError) {
      console.error('Ошибка удаления привычки:', deleteError);
      setError(deleteError.message ?? 'Не удалось удалить привычку');
    }
  };

  return (
    <div>
      <div className="section-header fc-section-header">
        <h2>Привычки</h2>
        <Button size="sm" variant="secondary" icon={<Plus size={16} />} id="addHabitBtn" onClick={openCreateModal} aria-label="Добавить привычку">
          Добавить
        </Button>
      </div>

      <HabitList
        habits={habits}
        isLoading={isLoading}
        error={error}
        onRetry={loadHabits}
        habitStates={habitStateMap}
        onComplete={handleCompleteHabit}
        onSkip={handleSkipHabit}
        onEdit={openEditModal}
        onDelete={handleDeleteHabit}
      />

      <HabitModal
        title="Новая привычка"
        isOpen={isCreateModalOpen}
        onClose={closeCreateModal}
        values={createForm}
        onChange={updateCreateForm}
        onSubmit={handleCreateHabit}
        submitLabel="Создать привычку"
        disabled={isSavingHabit}
        coinsInfo={createCoinsInfo}
        intelligenceInfo={createIntelInfo}
        satisfactionInfo={createSatisfactionInfo}
      />

      <HabitModal
        title="Редактировать привычку"
        isOpen={isEditModalOpen}
        onClose={closeEditModal}
        values={editForm}
        onChange={updateEditForm}
        onSubmit={handleUpdateHabit}
        submitLabel="Обновить привычку"
        disabled={isUpdatingHabit}
        coinsInfo={editCoinsInfo}
        intelligenceInfo={editIntelInfo}
        satisfactionInfo={editSatisfactionInfo}
      />

      <ConfirmModal
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ isOpen: false, habit: null })}
        onConfirm={handleDeleteConfirm}
        title="Удаление привычки"
        message="Удалить привычку?"
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />
    </div>
  );
}

