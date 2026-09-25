import React, { useCallback, useEffect, useState } from 'react';
import { Plus } from 'lucide-react';
import { Modal } from '../../components/common/Modal.jsx';
import { adminApi } from '../api.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';
import { StatValue } from '../../components/ui/icons.jsx';
import { ModalFormActions, PlaceBadge } from '../components/AdminBits.jsx';
import { COMPETITION_METRIC_LABELS } from '../labels.js';

const METRIC_OPTIONS = Object.entries(COMPETITION_METRIC_LABELS).map(([value, label]) => ({ value, label }));

const METRIC_LABELS = COMPETITION_METRIC_LABELS;

const emptyCompetitionForm = {
  id: null,
  name: '',
  description: '',
  start_time: '',
  end_time: '',
  metric_type: 'tasks_completed',
  target_value: '',
  first_place_coins: '',
  second_place_coins: '',
  third_place_coins: '',
  is_active: true
};

function toHumanDateTime(value) {
  if (!value) {
    return '—';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString('ru-RU');
}

function toInputDateTimeValue(value) {
  if (!value) {
    return '';
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  const tzOffsetMs = date.getTimezoneOffset() * 60 * 1000;
  const local = new Date(date.getTime() - tzOffsetMs);
  return local.toISOString().slice(0, 16);
}

export function CompetitionsSection({ isActive }) {
  const [competitions, setCompetitions] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [formData, setFormData] = useState(emptyCompetitionForm);
  const [isFormOpen, setIsFormOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, competitionId: null });
  const [finalizeConfirm, setFinalizeConfirm] = useState({ isOpen: false, competitionId: null });
  const [leaderboardModal, setLeaderboardModal] = useState({ isOpen: false, competitionId: null, leaderboard: [] });
  const [isLoadingLeaderboard, setIsLoadingLeaderboard] = useState(false);

  const loadCompetitions = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.listCompetitions();
      setCompetitions(Array.isArray(data) ? data : []);
    } catch (err) {
      console.error('Ошибка загрузки соревнований:', err);
      setError(err.message ?? 'Не удалось загрузить соревнования');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadCompetitions();
    }
  }, [isActive, loadCompetitions]);

  const handleOpenCreate = () => {
    setFormData(emptyCompetitionForm);
    setIsFormOpen(true);
  };

  const handleOpenEdit = (competition) => {
    setFormData({
      id: competition.id,
      name: competition.name || '',
      description: competition.description || '',
      start_time: toInputDateTimeValue(competition.start_time),
      end_time: toInputDateTimeValue(competition.end_time),
      metric_type: competition.metric_type || 'tasks_completed',
      target_value: competition.target_value || '',
      first_place_coins: competition.first_place_coins && competition.first_place_coins !== 0 ? String(competition.first_place_coins) : '',
      second_place_coins: competition.second_place_coins && competition.second_place_coins !== 0 ? String(competition.second_place_coins) : '',
      third_place_coins: competition.third_place_coins && competition.third_place_coins !== 0 ? String(competition.third_place_coins) : '',
      is_active: competition.is_active ?? true
    });
    setIsFormOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const payload = {
        name: formData.name,
        description: formData.description || null,
        start_time: new Date(formData.start_time).toISOString(),
        end_time: new Date(formData.end_time).toISOString(),
        metric_type: formData.metric_type || 'tasks_completed',
        target_value: formData.target_value ? parseInt(formData.target_value) : null,
        first_place_coins: formData.first_place_coins ? parseInt(formData.first_place_coins) : 0,
        second_place_coins: formData.second_place_coins ? parseInt(formData.second_place_coins) : 0,
        third_place_coins: formData.third_place_coins ? parseInt(formData.third_place_coins) : 0,
        is_active: formData.is_active
      };

      if (formData.id) {
        await adminApi.updateCompetition(formData.id, payload);
        setNotification({
          isOpen: true,
          message: 'Соревнование успешно обновлено',
          type: 'success',
          title: 'Успешно'
        });
      } else {
        await adminApi.createCompetition(payload);
        setNotification({
          isOpen: true,
          message: 'Соревнование успешно создано',
          type: 'success',
          title: 'Успешно'
        });
      }
      setIsFormOpen(false);
      await loadCompetitions();
    } catch (err) {
      console.error('Ошибка сохранения соревнования:', err);
      setNotification({
        isOpen: true,
        message: err.message ?? 'Не удалось сохранить соревнование',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = (competitionId) => {
    setDeleteConfirm({ isOpen: true, competitionId });
  };

  const handleDeleteConfirm = async () => {
    const { competitionId } = deleteConfirm;
    setDeleteConfirm({ isOpen: false, competitionId: null });
    setIsLoading(true);
    try {
      await adminApi.deleteCompetition(competitionId);
      setNotification({
        isOpen: true,
        message: 'Соревнование успешно удалено',
        type: 'success',
        title: 'Успешно'
      });
      await loadCompetitions();
    } catch (err) {
      console.error('Ошибка удаления соревнования:', err);
      setNotification({
        isOpen: true,
        message: err.message ?? 'Не удалось удалить соревнование',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleFinalize = (competitionId) => {
    setFinalizeConfirm({ isOpen: true, competitionId });
  };

  const handleFinalizeConfirm = async () => {
    const { competitionId } = finalizeConfirm;
    setFinalizeConfirm({ isOpen: false, competitionId: null });
    setIsLoading(true);
    try {
      await adminApi.finalizeCompetition(competitionId);
      setNotification({
        isOpen: true,
        message: 'Соревнование завершено. Награды выданы победителям.',
        type: 'success',
        title: 'Успешно'
      });
      await loadCompetitions();
    } catch (err) {
      console.error('Ошибка завершения соревнования:', err);
      setNotification({
        isOpen: true,
        message: err.message ?? 'Не удалось завершить соревнование',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsLoading(false);
    }
  };

  const handleShowLeaderboard = async (competitionId) => {
    setIsLoadingLeaderboard(true);
    try {
      const leaderboard = await adminApi.getCompetitionLeaderboard(competitionId);
      // Получить информацию о пользователях для топ-3
      const top3 = leaderboard.slice(0, 3);
      // Получить информацию о соревновании для метрики
      const competition = competitions.find(c => c.id === competitionId);
      setLeaderboardModal({ 
        isOpen: true, 
        competitionId, 
        leaderboard: top3,
        competition 
      });
    } catch (err) {
      console.error('Ошибка загрузки результатов:', err);
      setNotification({
        isOpen: true,
        message: err.message ?? 'Не удалось загрузить результаты',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsLoadingLeaderboard(false);
    }
  };

  if (!isActive) return null;

  const closeForm = () => {
    if (!isSubmitting) setIsFormOpen(false);
  };

  const statusBadge = (competition) => {
    if (competition.is_finished) return <Badge>Завершено</Badge>;
    if (competition.is_active) return <Badge tone="success">Активно</Badge>;
    return <Badge tone="warning">Не активно</Badge>;
  };

  const leaderboardMetricLabel = leaderboardModal.competition?.metric_type
    ? METRIC_LABELS[leaderboardModal.competition.metric_type] ?? 'Очков'
    : 'Очков';

  return (
    <section id="competitions-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Управление соревнованиями</h2>
        <Button size="sm" icon={<Plus size={16} aria-hidden="true" />} onClick={handleOpenCreate}>
          Создать соревнование
        </Button>
      </div>

      <div className="table-container">
        {isLoading ? (
          <StateView state="loading" message="Загрузка соревнований…" />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить соревнования" message={error} onRetry={loadCompetitions} />
        ) : !competitions.length ? (
          <StateView state="empty" title="Соревнований пока нет" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Метрика</th>
                <th>Начало</th>
                <th>Окончание</th>
                <th>Призы</th>
                <th>Статус</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {competitions.map((competition) => (
                <tr key={competition.id}>
                  <td>{competition.id}</td>
                  <td>{competition.name}</td>
                  <td className="admin-cell-clip" title={competition.description || undefined}>
                    {competition.description || '—'}
                  </td>
                  <td>{competition.metric_type ? METRIC_LABELS[competition.metric_type] ?? 'Другая метрика' : '—'}</td>
                  <td>{toHumanDateTime(competition.start_time)}</td>
                  <td>{toHumanDateTime(competition.end_time)}</td>
                  <td>
                    <div className="admin-prizes admin-inline">
                      {[competition.first_place_coins, competition.second_place_coins, competition.third_place_coins].map(
                        (coins, index) => (
                          <span key={index} className="admin-prize">
                            <PlaceBadge place={index + 1} />
                            <StatValue kind="coins" value={coins || 0} size={14} />
                          </span>
                        )
                      )}
                    </div>
                  </td>
                  <td>{statusBadge(competition)}</td>
                  <td>
                    <div className="action-buttons">
                      <Button size="sm" variant="secondary" onClick={() => handleOpenEdit(competition)}>
                        Редактировать
                      </Button>
                      {!competition.is_finished && (
                        <Button size="sm" onClick={() => handleFinalize(competition.id)}>
                          Завершить
                        </Button>
                      )}
                      {competition.is_finished && (
                        <Button size="sm" variant="secondary" onClick={() => handleShowLeaderboard(competition.id)}>
                          Результаты
                        </Button>
                      )}
                      <Button size="sm" variant="danger" onClick={() => handleDelete(competition.id)}>
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

      {/* Модальное окно формы */}
      <Modal
        isOpen={isFormOpen}
        onClose={closeForm}
        title={formData.id ? 'Редактировать соревнование' : 'Создать соревнование'}
        footer={
          <ModalFormActions
            formId="admin-competition-form"
            isSubmitting={isSubmitting}
            onCancel={closeForm}
            submitLabel={formData.id ? 'Сохранить' : 'Создать'}
          />
        }
      >
        <form id="admin-competition-form" className="admin-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="competition-name">Название *</label>
            <input
              id="competition-name"
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
            />
          </div>

          <div className="form-group">
            <label htmlFor="competition-description">Описание</label>
            <textarea
              id="competition-description"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              rows={4}
            />
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="competition-start">Время начала *</label>
              <input
                id="competition-start"
                type="datetime-local"
                value={formData.start_time}
                onChange={(e) => setFormData({ ...formData, start_time: e.target.value })}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="competition-end">Время окончания *</label>
              <input
                id="competition-end"
                type="datetime-local"
                value={formData.end_time}
                onChange={(e) => setFormData({ ...formData, end_time: e.target.value })}
                required
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="competition-metric">Условие соревнования (метрика) *</label>
            <select
              id="competition-metric"
              value={formData.metric_type}
              onChange={(e) => setFormData({ ...formData, metric_type: e.target.value })}
              required
            >
              {METRIC_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="competition-target">Целевое значение (необязательно)</label>
            <input
              id="competition-target"
              type="number"
              min="0"
              value={formData.target_value}
              onChange={(e) => setFormData({ ...formData, target_value: e.target.value })}
              placeholder="Например: 100"
            />
            <small className="form-hint">
              Значение метрики, которое нужно достичь. Если не указано, побеждает участник с наибольшим значением.
            </small>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label htmlFor="competition-first">1 место, монеты</label>
              <input
                id="competition-first"
                type="number"
                min="0"
                value={formData.first_place_coins === 0 || formData.first_place_coins === '0' ? '' : formData.first_place_coins}
                onChange={(e) => setFormData({ ...formData, first_place_coins: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label htmlFor="competition-second">2 место, монеты</label>
              <input
                id="competition-second"
                type="number"
                min="0"
                value={formData.second_place_coins === 0 || formData.second_place_coins === '0' ? '' : formData.second_place_coins}
                onChange={(e) => setFormData({ ...formData, second_place_coins: e.target.value })}
              />
            </div>
            <div className="form-group">
              <label htmlFor="competition-third">3 место, монеты</label>
              <input
                id="competition-third"
                type="number"
                min="0"
                value={formData.third_place_coins === 0 || formData.third_place_coins === '0' ? '' : formData.third_place_coins}
                onChange={(e) => setFormData({ ...formData, third_place_coins: e.target.value })}
              />
            </div>
          </div>

          <div className="form-group checkbox-group">
            <label htmlFor="competition-active">
              <input
                id="competition-active"
                type="checkbox"
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
              Активно
            </label>
          </div>
        </form>
      </Modal>

      {/* Модальное окно результатов */}
      <Modal
        isOpen={leaderboardModal.isOpen}
        onClose={() => setLeaderboardModal({ isOpen: false, competitionId: null, leaderboard: [], competition: null })}
        title="Результаты соревнования (топ-3)"
      >
        <div className="admin-modal">
          {isLoadingLeaderboard ? (
            <StateView state="loading" message="Загрузка результатов…" compact />
          ) : leaderboardModal.leaderboard.length === 0 ? (
            <StateView state="empty" title="Нет результатов" compact />
          ) : (
            <>
              {leaderboardModal.competition?.metric_type && (
                <div className="admin-note">
                  <strong>Условие соревнования:</strong> {leaderboardMetricLabel}
                  {leaderboardModal.competition.target_value ? `, цель: ${leaderboardModal.competition.target_value}` : ''}
                </div>
              )}
              <div className="admin-leaderboard">
                {leaderboardModal.leaderboard.map((participant, index) => (
                  <div key={participant.id} className="admin-leader">
                    <div className="admin-leader__who">
                      <PlaceBadge place={index + 1} large />
                      <strong>{index + 1} место</strong>
                      <span className="admin-muted">Пользователь #{participant.user_id}</span>
                    </div>
                    <div className="admin-leader__value">
                      {leaderboardMetricLabel}:{' '}
                      {participant.metric_value !== null && participant.metric_value !== undefined
                        ? participant.metric_value
                        : participant.score || 0}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
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
        onClose={() => setDeleteConfirm({ isOpen: false, competitionId: null })}
        onConfirm={handleDeleteConfirm}
        title="Удаление соревнования"
        message="Вы уверены, что хотите удалить это соревнование? Это действие необратимо."
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />

      <ConfirmModal
        isOpen={finalizeConfirm.isOpen}
        onClose={() => setFinalizeConfirm({ isOpen: false, competitionId: null })}
        onConfirm={handleFinalizeConfirm}
        title="Завершение соревнования"
        message="Завершить соревнование? Будет рассчитан рейтинг участников и выданы награды топ-3."
        confirmText="Завершить"
        cancelText="Отмена"
        type="warning"
      />
    </section>
  );
}

