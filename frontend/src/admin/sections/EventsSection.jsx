import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { Modal } from '../../components/common/Modal.jsx';
import { adminApi } from '../api.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';
import { ModalFormActions, RewardsCell } from '../components/AdminBits.jsx';

const emptyEventForm = {
  id: null,
  name: '',
  description: '',
  location: '',
  start_time: '',
  end_time: '',
  max_participants: '',
  is_public: true,
  reward_coins: '',
  reward_intelligence_points: '',
  group_ids: []
};

const emptyLessonForm = {
  id: null,
  name: '',
  description: '',
  location: '',
  start_time: '',
  end_time: '',
  reward_coins: '',
  reward_intelligence_points: '',
  group_ids: []
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

// Компонент для автообновления кода события каждые 15 секунд
function EventCodeDisplay({ eventId }) {
  const [code, setCode] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  const fetchCode = async () => {
    try {
      const response = await adminApi.getEventCode(eventId);
      setCode(response?.code || '');
      setIsLoading(false);
    } catch (error) {
      console.error('Ошибка загрузки кода:', error);
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCode();
    // Обновлять код каждые 15 секунд
    const interval = setInterval(fetchCode, 15000);
    return () => clearInterval(interval);
  }, [eventId]);

  if (isLoading) {
    return <div className="admin-code-loading">Загрузка кода…</div>;
  }

  return (
    <div className="admin-code">
      <div className="admin-code__digits" aria-live="polite">
        {code || '—'}
      </div>
    </div>
  );
}

// Экран преподавателя: ротируемый код + QR-диплинк на мини-приложение MAX
function LessonCodeDisplay({ lessonId }) {
  const [data, setData] = useState(null);
  const [qrUrl, setQrUrl] = useState(null);
  const [error, setError] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(null);

  useEffect(() => {
    let cancelled = false;
    let refreshTimer = null;
    let currentUrl = null;

    const load = async () => {
      try {
        const response = await adminApi.getLessonCode(lessonId);
        if (cancelled) return;
        setData(response);
        setError(null);
        setSecondsLeft(response?.expires_in_seconds ?? null);
        try {
          const url = await adminApi.getLessonQrImageUrl(lessonId);
          if (cancelled) {
            URL.revokeObjectURL(url);
            return;
          }
          if (currentUrl) URL.revokeObjectURL(currentUrl);
          currentUrl = url;
          setQrUrl(url);
        } catch (qrError) {
          console.warn('QR не загружен:', qrError);
        }
        // Обновляем сразу после смены окна кода
        refreshTimer = setTimeout(load, Math.max(1, response?.expires_in_seconds ?? 15) * 1000 + 300);
      } catch (loadError) {
        if (cancelled) return;
        setError(loadError?.message ?? 'Не удалось получить код');
        refreshTimer = setTimeout(load, 5000);
      }
    };
    load();
    const tick = setInterval(() => setSecondsLeft((value) => (value > 0 ? value - 1 : value)), 1000);
    return () => {
      cancelled = true;
      clearTimeout(refreshTimer);
      clearInterval(tick);
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [lessonId]);

  if (error) {
    return <div className="admin-code-error" role="alert">{error}</div>;
  }
  if (!data) {
    return <div className="admin-code-loading">Загрузка кода…</div>;
  }

  return (
    <div className="admin-code">
      {qrUrl ? <img className="admin-code__qr" src={qrUrl} alt="QR-код для отметки через MAX" /> : null}
      <div className="admin-code__digits" aria-live="polite">{data.code}</div>
      <div className="admin-code__hint">
        Студенты сканируют QR камерой (откроется мини-приложение MAX) или вводят код в приложении / боте: <code>/checkin {data.code}</code>
      </div>
      {secondsLeft != null ? <div className="admin-code__timer">Код обновится через {secondsLeft} с</div> : null}
      {!data.deep_link ? (
        <div className="admin-code__warning">MAX_BOT_USERNAME не задан — в QR записан только код, без ссылки на бота.</div>
      ) : null}
    </div>
  );
}

export function EventsSection({ isActive }) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [groups, setGroups] = useState([]);

  const [eventModalOpen, setEventModalOpen] = useState(false);
  const [lessonModalOpen, setLessonModalOpen] = useState(false);
  const [qrModalState, setQrModalState] = useState({ isOpen: false, eventId: null, lessonId: null });
  const [attendancesModalState, setAttendancesModalState] = useState({ isOpen: false, eventId: null, lessonId: null, attendances: [], allMembers: [] });

  const [eventForm, setEventForm] = useState(emptyEventForm);
  const [lessonForm, setLessonForm] = useState(emptyLessonForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, type: null, id: null, onConfirm: null });

  const [events, setEvents] = useState([]);
  const [lessons, setLessons] = useState([]);

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [eventsData, lessonsData] = await Promise.all([adminApi.listEvents(), adminApi.listLessons()]);
      const eventsList = Array.isArray(eventsData)
        ? eventsData.map((event) => ({ type: 'event', ...event })).sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
        : [];
      const lessonsList = Array.isArray(lessonsData)
        ? lessonsData.map((lesson) => ({ type: 'lesson', ...lesson })).sort((a, b) => new Date(a.start_time) - new Date(b.start_time))
        : [];
      
      setEvents(eventsList);
      setLessons(lessonsList);
      setItems([...eventsList, ...lessonsList]); // Для обратной совместимости
    } catch (loadError) {
      console.error('Ошибка загрузки событий:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить события и занятия');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadData();
    }
  }, [isActive, loadData]);

  useEffect(() => {
    if (!isActive) {
      return;
    }
    adminApi
      .listGroups()
      .then((list) => setGroups(Array.isArray(list) ? list : []))
      .catch((err) => {
        console.error('Ошибка загрузки групп:', err);
        setGroups([]);
      });
  }, [isActive]);

  const groupsMap = useMemo(
    () =>
      groups.reduce((acc, group) => {
        acc[group.id] = group;
        return acc;
      }, {}),
    [groups]
  );

  const handleOpenEventCreate = () => {
    setEventForm(emptyEventForm);
    setEventModalOpen(true);
  };

  const handleOpenEventEdit = async (eventId) => {
    setIsSubmitting(true);
    try {
      const event = await adminApi.getEvent(eventId);
      setEventForm({
        id: event.id,
        name: event.name ?? '',
        description: event.description ?? '',
        location: event.location ?? '',
        start_time: toInputDateTimeValue(event.start_time),
        end_time: toInputDateTimeValue(event.end_time),
        max_participants: event.max_participants ?? '',
        is_public: Boolean(event.is_public),
        reward_coins: event.reward_coins && event.reward_coins !== 0 ? String(event.reward_coins) : '',
        reward_intelligence_points: event.reward_intelligence_points && event.reward_intelligence_points !== 0 ? String(event.reward_intelligence_points) : '',
        group_ids: Array.isArray(event.groups) ? event.groups.map((group) => group.id) : []
      });
      setEventModalOpen(true);
    } catch (loadError) {
      console.error('Ошибка загрузки события:', loadError);
      setNotification({
        isOpen: true,
        message: loadError.message ?? 'Не удалось загрузить событие',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleEventSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const payload = {
        name: eventForm.name.trim(),
        description: eventForm.description.trim() || null,
        location: eventForm.location.trim() || null,
        start_time: eventForm.start_time,
        end_time: eventForm.end_time || null,
        max_participants: eventForm.max_participants ? Number(eventForm.max_participants) : null,
        is_public: Boolean(eventForm.is_public),
        reward_coins: Number(eventForm.reward_coins) || 0,
        reward_intelligence_points: Number(eventForm.reward_intelligence_points) || 0,
        group_ids: eventForm.group_ids || []
      };

      if (!payload.name || !payload.start_time) {
        throw new Error('Название и дата начала обязательны');
      }

      if (eventForm.id) {
        await adminApi.updateEvent(eventForm.id, payload);
      } else {
        await adminApi.createEvent(payload);
      }

      setEventModalOpen(false);
      setEventForm(emptyEventForm);
      await loadData();
    } catch (submitError) {
      console.error('Ошибка сохранения события:', submitError);
      setNotification({
        isOpen: true,
        message: submitError.message ?? 'Не удалось сохранить событие',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteEvent = async (eventId) => {
    setDeleteConfirm({
      isOpen: true,
      type: 'event',
      id: eventId,
      onConfirm: async () => {
    try {
      await adminApi.deleteEvent(eventId);
      await loadData();
    } catch (deleteError) {
      console.error('Ошибка удаления события:', deleteError);
          setNotification({
            isOpen: true,
            message: deleteError.message ?? 'Не удалось удалить событие',
            type: 'error',
            title: 'Ошибка'
          });
    }
      }
    });
  };

  const handleOpenLessonCreate = () => {
    setLessonForm({ ...emptyLessonForm, group_ids: [] });
    setLessonModalOpen(true);
  };

  const handleOpenLessonEdit = async (lessonId) => {
    setIsSubmitting(true);
    try {
      const lesson = await adminApi.getLesson(lessonId);
      setLessonForm({
        id: lesson.id,
        name: lesson.name ?? '',
        description: lesson.description ?? '',
        location: lesson.location ?? '',
        start_time: toInputDateTimeValue(lesson.start_time),
        end_time: toInputDateTimeValue(lesson.end_time),
        reward_coins: lesson.reward_coins && lesson.reward_coins !== 0 ? String(lesson.reward_coins) : '',
        reward_intelligence_points: lesson.reward_intelligence_points && lesson.reward_intelligence_points !== 0 ? String(lesson.reward_intelligence_points) : '',
        group_ids: Array.isArray(lesson.groups) ? lesson.groups.map((group) => group.id) : []
      });
      setLessonModalOpen(true);
    } catch (loadError) {
      console.error('Ошибка загрузки занятия:', loadError);
      setNotification({
        isOpen: true,
        message: loadError.message ?? 'Не удалось загрузить занятие',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLessonSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const payload = {
        name: lessonForm.name.trim(),
        description: lessonForm.description.trim() || null,
        location: lessonForm.location.trim() || null,
        start_time: lessonForm.start_time,
        end_time: lessonForm.end_time,
        reward_coins: Number(lessonForm.reward_coins) || 0,
        reward_intelligence_points: Number(lessonForm.reward_intelligence_points) || 0,
        group_ids: lessonForm.group_ids
      };

      if (!payload.name || !payload.start_time || !payload.end_time) {
        throw new Error('Название и даты обязательны');
      }
      if (!payload.group_ids.length) {
        throw new Error('Выберите хотя бы одну группу');
      }

      if (lessonForm.id) {
        await adminApi.updateLesson(lessonForm.id, payload);
      } else {
        await adminApi.createLesson({ ...payload, created_by: 1 });
      }

      setLessonModalOpen(false);
      setLessonForm(emptyLessonForm);
      await loadData();
    } catch (submitError) {
      console.error('Ошибка сохранения занятия:', submitError);
      setNotification({
        isOpen: true,
        message: submitError.message ?? 'Не удалось сохранить занятие',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteLesson = async (lessonId) => {
    setDeleteConfirm({
      isOpen: true,
      type: 'lesson',
      id: lessonId,
      onConfirm: async () => {
    try {
      await adminApi.deleteLesson(lessonId);
      await loadData();
    } catch (deleteError) {
      console.error('Ошибка удаления занятия:', deleteError);
          setNotification({
            isOpen: true,
            message: deleteError.message ?? 'Не удалось удалить занятие',
            type: 'error',
            title: 'Ошибка'
          });
    }
      }
    });
  };

  const handleShowEventCode = async (eventId) => {
    setQrModalState({ isOpen: true, eventId, lessonId: null });
  };

  const handleShowLessonCode = async (lessonId) => {
    setQrModalState({ isOpen: true, eventId: null, lessonId });
  };

  const handleShowAttendances = async (eventId) => {
    try {
      const attendances = await adminApi.getEventAttendances(eventId);
      setAttendancesModalState({ isOpen: true, eventId, lessonId: null, attendances: Array.isArray(attendances) ? attendances : [], allMembers: [] });
    } catch (error) {
      console.error('Ошибка загрузки участников:', error);
      setNotification({
        isOpen: true,
        message: error.message ?? 'Не удалось загрузить участников',
        type: 'error',
        title: 'Ошибка'
      });
    }
  };

  const handleShowLessonAttendances = async (lessonId, lessonGroups) => {
    try {
      const attendances = await adminApi.getLessonAttendances(lessonId);
      const attendedUserIds = new Set((Array.isArray(attendances) ? attendances : []).map(a => a.user_id));
      
      // Получаем всех участников групп занятия
      const allMembers = [];
      if (lessonGroups && Array.isArray(lessonGroups) && lessonGroups.length > 0) {
        for (const group of lessonGroups) {
          try {
            const members = await adminApi.getGroupMembers(group.id, 1); // Используем user_id=1 для админки
            if (Array.isArray(members)) {
              allMembers.push(...members.map(m => ({
                ...m,
                group_id: group.id,
                group_name: group.name,
                attended: attendedUserIds.has(m.user_id)
              })));
            }
          } catch (err) {
            console.error(`Ошибка загрузки участников группы ${group.id}:`, err);
          }
        }
      }
      
      setAttendancesModalState({ 
        isOpen: true, 
        eventId: null, 
        lessonId, 
        attendances: Array.isArray(attendances) ? attendances : [], 
        allMembers 
      });
    } catch (error) {
      console.error('Ошибка загрузки посещаемости занятия:', error);
      setNotification({
        isOpen: true,
        message: error.message ?? 'Не удалось загрузить посещаемость',
        type: 'error',
        title: 'Ошибка'
      });
    }
  };


  return (
    <section id="events-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Управление событиями и занятиями</h2>
        <div className="section-actions">
          <Button size="sm" icon={<Plus size={16} aria-hidden="true" />} onClick={handleOpenLessonCreate} disabled={isSubmitting}>
            Создать занятие
          </Button>
          <Button
            size="sm"
            variant="secondary"
            icon={<Plus size={16} aria-hidden="true" />}
            onClick={handleOpenEventCreate}
            disabled={isSubmitting}
          >
            Создать событие
          </Button>
        </div>
      </div>

      {/* Блок занятий */}
      <div className="admin-block">
        <div className="section-header section-header--sub">
          <h3>Занятия</h3>
        </div>
      <div className="table-container">
        {isLoading ? (
            <StateView state="loading" message="Загрузка занятий…" />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить занятия" message={error} onRetry={loadData} />
          ) : !lessons.length ? (
            <StateView state="empty" title="Занятий пока нет" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Место</th>
                <th>Начало</th>
                <th>Конец</th>
                  <th>Группы</th>
                <th>Награды</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
                {lessons.map((item) => {
                  const lessonGroups =
                    Array.isArray(item.groups) && item.groups.length
                      ? item.groups.map((group) => group.name).join(', ')
                      : 'Нет групп';

                  return (
                    <tr key={`lesson-${item.id}`}>
                      <td>{item.id}</td>
                      <td>{item.name}</td>
                      <td>{item.description || '—'}</td>
                      <td>{item.location || '—'}</td>
                      <td>{toHumanDateTime(item.start_time)}</td>
                      <td>{toHumanDateTime(item.end_time)}</td>
                      <td>{lessonGroups}</td>
                      <td>
                        <RewardsCell coins={item.reward_coins} intelligence={item.reward_intelligence_points} />
                      </td>
                      <td>
                        <div className="action-buttons">
                          <Button size="sm" onClick={() => handleShowLessonCode(item.id)}>
                            Код
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => handleShowLessonAttendances(item.id, item.groups)}>
                            Посещаемость
                          </Button>
                          <Button size="sm" variant="secondary" onClick={() => handleOpenLessonEdit(item.id)}>
                            Редактировать
                          </Button>
                          <Button size="sm" variant="danger" onClick={() => handleDeleteLesson(item.id)}>
                            Удалить
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Блок событий */}
      <div>
        <div className="section-header section-header--sub">
          <h3>События</h3>
        </div>
        <div className="table-container">
          {isLoading ? (
            <StateView state="loading" message="Загрузка событий…" />
          ) : error ? (
            <StateView state="error" title="Не удалось загрузить события" message={error} onRetry={loadData} />
          ) : !events.length ? (
            <StateView state="empty" title="Событий пока нет" />
          ) : (
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Описание</th>
                  <th>Место</th>
                  <th>Начало</th>
                  <th>Конец</th>
                  <th>Группы / Макс. участников</th>
                  <th>Награды</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody>
                {events.map((item) => {
                  const eventGroups =
                  Array.isArray(item.groups) && item.groups.length
                    ? item.groups.map((group) => group.name).join(', ')
                      : item.is_public
                      ? 'Все пользователи'
                    : 'Нет групп';
                return (
                    <tr key={`event-${item.id}`}>
                    <td>{item.id}</td>
                    <td>{item.name}</td>
                    <td>{item.description || '—'}</td>
                    <td>{item.location || '—'}</td>
                    <td>{toHumanDateTime(item.start_time)}</td>
                    <td>{toHumanDateTime(item.end_time)}</td>
                      <td>
                        {eventGroups}
                        {item.max_participants ? ` (Макс: ${item.max_participants})` : ''}
                      </td>
                    <td>
                      <RewardsCell coins={item.reward_coins} intelligence={item.reward_intelligence_points} />
                    </td>
                    <td>
                      <div className="action-buttons">
                        <Button size="sm" onClick={() => handleShowEventCode(item.id)}>
                          Код
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => handleShowAttendances(item.id)}>
                          Участники
                        </Button>
                        <Button size="sm" variant="secondary" onClick={() => handleOpenEventEdit(item.id)}>
                          Редактировать
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => handleDeleteEvent(item.id)}>
                          Удалить
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
        </div>
      </div>

      <Modal
        isOpen={eventModalOpen}
        onClose={() => {
          if (!isSubmitting) {
            setEventModalOpen(false);
            setEventForm(emptyEventForm);
          }
        }}
        title={eventForm.id ? 'Редактировать событие' : 'Создать событие'}
        footer={
          <ModalFormActions
            formId="admin-event-form"
            isSubmitting={isSubmitting}
            onCancel={() => {
              if (!isSubmitting) {
                setEventModalOpen(false);
                setEventForm(emptyEventForm);
              }
            }}
          />
        }
      >
        <form id="admin-event-form" className="admin-form" onSubmit={handleEventSubmit}>
          <div className="form-group">
            <label htmlFor="event-name">Название *</label>
            <input
              id="event-name"
              type="text"
              value={eventForm.name}
              onChange={(e) => setEventForm((prev) => ({ ...prev, name: e.target.value }))}
              required
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="event-description">Описание</label>
            <textarea
              id="event-description"
              rows={3}
              value={eventForm.description}
              onChange={(e) => setEventForm((prev) => ({ ...prev, description: e.target.value }))}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="event-location">Место</label>
            <input
              id="event-location"
              type="text"
              value={eventForm.location}
              onChange={(e) => setEventForm((prev) => ({ ...prev, location: e.target.value }))}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="event-start">Начало *</label>
              <input
                id="event-start"
                type="datetime-local"
                value={eventForm.start_time}
                onChange={(e) => setEventForm((prev) => ({ ...prev, start_time: e.target.value }))}
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="event-end">Конец</label>
              <input
                id="event-end"
                type="datetime-local"
                value={eventForm.end_time}
                onChange={(e) => setEventForm((prev) => ({ ...prev, end_time: e.target.value }))}
                disabled={isSubmitting}
              />
            </div>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="event-max">Макс. участников</label>
              <input
                id="event-max"
                type="number"
                min="1"
                value={eventForm.max_participants}
                onChange={(e) => setEventForm((prev) => ({ ...prev, max_participants: e.target.value }))}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="event-reward-coins">Монеты</label>
              <input
                id="event-reward-coins"
                type="number"
                min="0"
                value={eventForm.reward_coins === 0 || eventForm.reward_coins === '0' ? '' : eventForm.reward_coins}
                onChange={(e) => setEventForm((prev) => ({ ...prev, reward_coins: e.target.value }))}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="event-reward-intelligence">Интеллект</label>
              <input
                id="event-reward-intelligence"
                type="number"
                min="0"
                value={eventForm.reward_intelligence_points === 0 || eventForm.reward_intelligence_points === '0' ? '' : eventForm.reward_intelligence_points}
                onChange={(e) => setEventForm((prev) => ({ ...prev, reward_intelligence_points: e.target.value }))}
                disabled={isSubmitting}
              />
            </div>
          </div>
          <div className="form-group checkbox-group">
            <label htmlFor="event-public">
              <input
                id="event-public"
                type="checkbox"
                checked={eventForm.is_public}
                onChange={(e) => setEventForm((prev) => ({ ...prev, is_public: e.target.checked }))}
                disabled={isSubmitting}
              />
              Публичное событие
            </label>
          </div>
          <div className="form-group">
            <label htmlFor="event-groups">Группы</label>
            <select
              id="event-groups"
              multiple
              size={Math.min(8, Math.max(groups.length, 4))}
              value={eventForm.group_ids.map(String)}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions).map((option) => Number(option.value));
                setEventForm((prev) => ({ ...prev, group_ids: selected }));
              }}
              disabled={isSubmitting}
            >
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
            <small className="form-hint">Удерживайте Ctrl (Cmd) для выбора нескольких групп. Оставьте пустым для публичного события.</small>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={lessonModalOpen}
        onClose={() => {
          if (!isSubmitting) {
            setLessonModalOpen(false);
            setLessonForm(emptyLessonForm);
          }
        }}
        title={lessonForm.id ? 'Редактировать занятие' : 'Создать занятие'}
        footer={
          <ModalFormActions
            formId="admin-lesson-form"
            isSubmitting={isSubmitting}
            onCancel={() => {
              if (!isSubmitting) {
                setLessonModalOpen(false);
                setLessonForm(emptyLessonForm);
              }
            }}
          />
        }
      >
        <form id="admin-lesson-form" className="admin-form" onSubmit={handleLessonSubmit}>
          <div className="form-group">
            <label htmlFor="lesson-name">Название *</label>
            <input
              id="lesson-name"
              type="text"
              value={lessonForm.name}
              onChange={(e) => setLessonForm((prev) => ({ ...prev, name: e.target.value }))}
              required
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="lesson-description">Описание</label>
            <textarea
              id="lesson-description"
              rows={3}
              value={lessonForm.description}
              onChange={(e) => setLessonForm((prev) => ({ ...prev, description: e.target.value }))}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="lesson-location">Место</label>
            <input
              id="lesson-location"
              type="text"
              value={lessonForm.location}
              onChange={(e) => setLessonForm((prev) => ({ ...prev, location: e.target.value }))}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="lesson-start">Начало *</label>
              <input
                id="lesson-start"
                type="datetime-local"
                value={lessonForm.start_time}
                onChange={(e) => setLessonForm((prev) => ({ ...prev, start_time: e.target.value }))}
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="lesson-end">Конец *</label>
              <input
                id="lesson-end"
                type="datetime-local"
                value={lessonForm.end_time}
                onChange={(e) => setLessonForm((prev) => ({ ...prev, end_time: e.target.value }))}
                required
                disabled={isSubmitting}
              />
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="lesson-groups">Группы *</label>
            <select
              id="lesson-groups"
              multiple
              size={Math.min(8, Math.max(groups.length, 4))}
              value={lessonForm.group_ids.map(String)}
              onChange={(e) => {
                const selected = Array.from(e.target.selectedOptions).map((option) => Number(option.value));
                setLessonForm((prev) => ({ ...prev, group_ids: selected }));
              }}
              required
              disabled={isSubmitting}
            >
              {groups.map((group) => (
                <option key={group.id} value={group.id}>
                  {group.name}
                </option>
              ))}
            </select>
            <small className="form-hint">Удерживайте Ctrl (Cmd) для выбора нескольких групп</small>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="lesson-reward-coins">Монеты</label>
              <input
                id="lesson-reward-coins"
                type="number"
                min="0"
                value={lessonForm.reward_coins === 0 || lessonForm.reward_coins === '0' ? '' : lessonForm.reward_coins}
                onChange={(e) => setLessonForm((prev) => ({ ...prev, reward_coins: e.target.value }))}
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="lesson-reward-intelligence">Интеллект</label>
              <input
                id="lesson-reward-intelligence"
                type="number"
                min="0"
                value={lessonForm.reward_intelligence_points === 0 || lessonForm.reward_intelligence_points === '0' ? '' : lessonForm.reward_intelligence_points}
                onChange={(e) =>
                  setLessonForm((prev) => ({ ...prev, reward_intelligence_points: e.target.value }))
                }
                disabled={isSubmitting}
              />
            </div>
          </div>
        </form>
      </Modal>

      <Modal
        isOpen={qrModalState.isOpen}
        onClose={() => setQrModalState({ isOpen: false, eventId: null, lessonId: null })}
        title={qrModalState.lessonId ? "Код для занятия" : "Код для события"}
      >
        <div className="admin-modal">
          {qrModalState.eventId ? (
            <EventCodeDisplay eventId={qrModalState.eventId} />
          ) : null}
          {qrModalState.lessonId ? (
            <LessonCodeDisplay lessonId={qrModalState.lessonId} />
          ) : null}
          <p className="admin-code__hint admin-code__hint--center">
            {qrModalState.lessonId 
              ? "Покажите экран аудитории: QR и код меняются автоматически. Отметиться можно только во время пары."
              : "Пользователи могут ввести этот 4-значный код для отметки посещения события. Код обновляется каждые 15 секунд."}
          </p>
        </div>
      </Modal>

      <Modal
        isOpen={attendancesModalState.isOpen}
        onClose={() => setAttendancesModalState({ isOpen: false, eventId: null, lessonId: null, attendances: [], allMembers: [] })}
        title={attendancesModalState.lessonId ? "Посещаемость занятия" : "Участники события"}
      >
        <div className="admin-modal">
          {attendancesModalState.lessonId ? (
            // Для занятий показываем всех участников групп (кто пришёл, кто нет)
            <div>
              <h3>Участники групп ({attendancesModalState.allMembers.length})</h3>
              {attendancesModalState.allMembers.length === 0 ? (
                <p className="admin-empty-note">Нет участников в группах занятия</p>
              ) : (
                <div className="admin-modal-table-wrap">
                  <table className="admin-modal-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Группа</th>
                        <th>Статус</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attendancesModalState.allMembers.map((member) => {
                        const attendance = attendancesModalState.attendances.find((a) => a.user_id === member.user_id);
                        return (
                          <tr key={`${member.group_id}-${member.user_id}`}>
                            <td>{member.user_id}</td>
                            <td>{member.user?.username || `Пользователь #${member.user_id}`}</td>
                            <td>{member.group_name || `Группа #${member.group_id}`}</td>
                            <td>
                              {attendance ? (
                                <Badge tone="success">Пришёл · {toHumanDateTime(attendance.attended_at)}</Badge>
                              ) : (
                                <Badge tone="danger">Не пришёл</Badge>
                              )}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          ) : (
            // Для событий показываем зарегистрированных
            <div>
              <h3>Зарегистрированные ({attendancesModalState.attendances.length})</h3>
              {attendancesModalState.attendances.length === 0 ? (
                <p className="admin-empty-note">Нет зарегистрированных участников</p>
              ) : (
                <div className="admin-modal-table-wrap">
                  <table className="admin-modal-table">
                    <thead>
                      <tr>
                        <th>ID</th>
                        <th>Имя</th>
                        <th>Эл. почта</th>
                        <th>Зарегистрирован</th>
                        <th>Посетил</th>
                      </tr>
                    </thead>
                    <tbody>
                      {attendancesModalState.attendances.map((attendance) => (
                        <tr key={attendance.id}>
                          <td>{attendance.user_id}</td>
                          <td>{attendance.user_name || '—'}</td>
                          <td>{attendance.user_email || '—'}</td>
                          <td>{toHumanDateTime(attendance.registered_at)}</td>
                          <td>
                            {attendance.attended ? (
                              <Badge tone="success">{toHumanDateTime(attendance.attended_at)}</Badge>
                            ) : (
                              <Badge>Не посетил</Badge>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
          <div>
            <h3>Посетившие ({attendancesModalState.attendances.filter((a) => a.attended).length})</h3>
            {attendancesModalState.attendances.filter((a) => a.attended).length === 0 ? (
              <p className="admin-empty-note">Нет посетивших участников</p>
            ) : (
              <div className="admin-modal-table-wrap">
                <table className="admin-modal-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Имя</th>
                      <th>Эл. почта</th>
                      <th>Время посещения</th>
                    </tr>
                  </thead>
                  <tbody>
                    {attendancesModalState.attendances
                      .filter((a) => a.attended)
                      .map((attendance) => (
                        <tr key={attendance.id}>
                          <td>{attendance.user_id}</td>
                          <td>{attendance.user_name || '—'}</td>
                          <td>{attendance.user_email || '—'}</td>
                          <td>{toHumanDateTime(attendance.attended_at)}</td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
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
        onClose={() => setDeleteConfirm({ ...deleteConfirm, isOpen: false })}
        onConfirm={() => {
          if (deleteConfirm.onConfirm) {
            deleteConfirm.onConfirm();
          }
          setDeleteConfirm({ ...deleteConfirm, isOpen: false });
        }}
        title={deleteConfirm.type === 'event' ? 'Удаление события' : 'Удаление занятия'}
        message={deleteConfirm.type === 'event' ? 'Удалить событие?' : 'Удалить занятие?'}
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />
    </section>
  );
}


