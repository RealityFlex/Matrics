import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { Modal } from '../../components/common/Modal.jsx';
import { adminApi, ACHIEVEMENT_REQUIREMENT_TYPES } from '../api.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';
import { ModalFormActions, RequirementIcon, RewardsCell } from '../components/AdminBits.jsx';
import { REQUIREMENT_TYPE_LABELS } from '../labels.js';

const emptyAchievement = {
  id: null,
  name: '',
  description: '',
  requirement_type: ACHIEVEMENT_REQUIREMENT_TYPES[0].value,
  requirement_value: 1,
  reward_coins: '',
  reward_intelligence_points: '',
  is_hidden: false
};

export function AchievementsSection({ isActive }) {
  const [achievements, setAchievements] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formState, setFormState] = useState(emptyAchievement);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, achievementId: null });

  const requirementTypeMap = useMemo(
    () =>
      ACHIEVEMENT_REQUIREMENT_TYPES.reduce(
        (acc, option) => {
          acc[option.value] = option.label;
          return acc;
        },
        { ...REQUIREMENT_TYPE_LABELS }
      ),
    []
  );

  const loadAchievements = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.listAchievements();
      setAchievements(Array.isArray(data) ? data : []);
    } catch (loadError) {
      console.error('Ошибка загрузки достижений:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить достижения');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadAchievements();
    }
  }, [isActive, loadAchievements]);

  const handleOpenCreate = () => {
    setFormState(emptyAchievement);
    setIsModalOpen(true);
  };

  const handleOpenEdit = async (achievementId) => {
    setIsSubmitting(true);
    try {
      const achievement = await adminApi.getAchievement(achievementId);
      setFormState({
        id: achievement.id,
        name: achievement.name ?? '',
        description: achievement.description ?? '',
        requirement_type: achievement.requirement_type ?? ACHIEVEMENT_REQUIREMENT_TYPES[0].value,
        requirement_value: achievement.requirement_value ?? 1,
        reward_coins: achievement.reward_coins && achievement.reward_coins !== 0 ? String(achievement.reward_coins) : '',
        reward_intelligence_points: achievement.reward_intelligence_points && achievement.reward_intelligence_points !== 0 ? String(achievement.reward_intelligence_points) : '',
        is_hidden: Boolean(achievement.is_hidden)
      });
      setIsModalOpen(true);
    } catch (loadError) {
      console.error('Ошибка загрузки достижения:', loadError);
      setNotification({
        isOpen: true,
        message: loadError.message ?? 'Не удалось загрузить достижение',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const payload = {
        name: formState.name.trim(),
        description: formState.description.trim() || null,
        requirement_type: formState.requirement_type,
        requirement_value: Number(formState.requirement_value) || 0,
        reward_coins: formState.reward_coins ? Number(formState.reward_coins) : 0,
        reward_intelligence_points: formState.reward_intelligence_points ? Number(formState.reward_intelligence_points) : 0,
        is_hidden: Boolean(formState.is_hidden)
      };

      if (!payload.name) {
        throw new Error('Название обязательно');
      }

      if (payload.requirement_value <= 0) {
        throw new Error('Значение требования должно быть больше нуля');
      }

      if (formState.id) {
        await adminApi.updateAchievement(formState.id, payload);
      } else {
        await adminApi.createAchievement(payload);
      }

      setIsModalOpen(false);
      setFormState(emptyAchievement);
      await loadAchievements();
    } catch (submitError) {
      console.error('Ошибка сохранения достижения:', submitError);
      setNotification({
        isOpen: true,
        message: submitError.message ?? 'Не удалось сохранить достижение',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (achievementId) => {
    setDeleteConfirm({ isOpen: true, achievementId });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.achievementId) return;
    try {
      await adminApi.deleteAchievement(deleteConfirm.achievementId);
      await loadAchievements();
      setDeleteConfirm({ isOpen: false, achievementId: null });
    } catch (deleteError) {
      console.error('Ошибка удаления достижения:', deleteError);
      setNotification({
        isOpen: true,
        message: deleteError.message ?? 'Не удалось удалить достижение',
        type: 'error',
        title: 'Ошибка'
      });
      setDeleteConfirm({ isOpen: false, achievementId: null });
    }
  };

  return (
    <section id="achievements-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Управление достижениями</h2>
        <Button size="sm" icon={<Plus size={16} aria-hidden="true" />} onClick={handleOpenCreate} disabled={isSubmitting}>
          Создать достижение
        </Button>
      </div>
      <div className="table-container">
        {isLoading ? (
          <StateView state="loading" message="Загрузка достижений…" />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить достижения" message={error} onRetry={loadAchievements} />
        ) : !achievements.length ? (
          <StateView state="empty" title="Достижений пока нет" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Тип требования</th>
                <th>Значение</th>
                <th>Награды</th>
                <th>Скрыто</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {achievements.map((achievement) => (
                <tr key={achievement.id}>
                  <td>{achievement.id}</td>
                  <td>{achievement.name}</td>
                  <td>{achievement.description || '—'}</td>
                  <td>
                    <span className="admin-icon-label">
                      <RequirementIcon type={achievement.requirement_type} />
                      {requirementTypeMap[achievement.requirement_type] ?? 'Другое условие'}
                    </span>
                  </td>
                  <td>{achievement.requirement_value}</td>
                  <td>
                    <RewardsCell coins={achievement.reward_coins} intelligence={achievement.reward_intelligence_points} />
                  </td>
                  <td>{achievement.is_hidden ? <Badge>Скрыто</Badge> : <span className="admin-muted">Нет</span>}</td>
                  <td>
                    <div className="action-buttons">
                      <Button size="sm" variant="secondary" onClick={() => handleOpenEdit(achievement.id)}>
                        Редактировать
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => handleDelete(achievement.id)}>
                        Удалить
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          if (!isSubmitting) {
            setIsModalOpen(false);
            setFormState(emptyAchievement);
          }
        }}
        title={formState.id ? 'Редактировать достижение' : 'Создать достижение'}
        footer={
          <ModalFormActions
            formId="admin-achievement-form"
            isSubmitting={isSubmitting}
            onCancel={() => {
              if (!isSubmitting) {
                setIsModalOpen(false);
                setFormState(emptyAchievement);
              }
            }}
          />
        }
      >
        <form id="admin-achievement-form" className="admin-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="achievement-name">Название *</label>
            <input
              id="achievement-name"
              type="text"
              value={formState.name}
              onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
              required
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="achievement-description">Описание</label>
            <textarea
              id="achievement-description"
              rows={3}
              value={formState.description}
              onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="achievement-requirement-type">Тип требования *</label>
            <select
              id="achievement-requirement-type"
              value={formState.requirement_type}
              onChange={(event) => setFormState((prev) => ({ ...prev, requirement_type: event.target.value }))}
              required
              disabled={isSubmitting}
            >
              {ACHIEVEMENT_REQUIREMENT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="achievement-requirement-value">Значение *</label>
              <input
                id="achievement-requirement-value"
                type="number"
                min="1"
                value={formState.requirement_value}
                onChange={(event) => setFormState((prev) => ({ ...prev, requirement_value: event.target.value }))}
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="achievement-reward-coins">Награда: монеты</label>
              <input
                id="achievement-reward-coins"
                type="number"
                min="0"
                value={formState.reward_coins === 0 || formState.reward_coins === '0' ? '' : formState.reward_coins}
                onChange={(event) => setFormState((prev) => ({ ...prev, reward_coins: event.target.value }))}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="achievement-reward-intelligence">Награда: интеллект</label>
              <input
                id="achievement-reward-intelligence"
                type="number"
                min="0"
                value={formState.reward_intelligence_points === 0 || formState.reward_intelligence_points === '0' ? '' : formState.reward_intelligence_points}
                onChange={(event) =>
                  setFormState((prev) => ({ ...prev, reward_intelligence_points: event.target.value }))
                }
                disabled={isSubmitting}
              />
            </div>
          </div>
          <div className="form-group checkbox-group">
            <label htmlFor="achievement-hidden">
              <input
                id="achievement-hidden"
                type="checkbox"
                checked={formState.is_hidden}
                onChange={(event) => setFormState((prev) => ({ ...prev, is_hidden: event.target.checked }))}
                disabled={isSubmitting}
              />
              Скрытое достижение
            </label>
          </div>
        </form>
        </Modal>
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
      <ConfirmModal
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ isOpen: false, achievementId: null })}
        onConfirm={handleDeleteConfirm}
        title="Удаление достижения"
        message="Удалить достижение?"
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />
    </section>
  );
}


