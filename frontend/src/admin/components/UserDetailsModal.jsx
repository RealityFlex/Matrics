import React, { useState, useEffect } from 'react';
import { ChevronDown, ChevronRight, FileDown } from 'lucide-react';
import { adminApi } from '../api.js';
import { Modal } from '../../components/common/Modal.jsx';
import { exportUserToPDF } from '../utils/pdfExport.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { Button, StateView } from '../../components/ui/index.jsx';
import { StatValue } from '../../components/ui/icons.jsx';
import {
  GOAL_STATUS_LABELS,
  HABIT_FREQUENCY_LABELS,
  RARITY_LABELS,
  ROLE_LABELS,
  TASK_PRIORITY_LABELS,
  TASK_STATUS_LABELS,
  labelFor
} from '../labels.js';

export function UserDetailsModal({ isOpen, onClose, userId }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [data, setData] = useState(null);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });

  useEffect(() => {
    if (isOpen && userId) {
      loadUserData();
    } else {
      setData(null);
      setError(null);
    }
  }, [isOpen, userId]);

  const loadUserData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [
        user,
        character,
        habitStats,
        taskStats,
        eventStats,
        achievementStats,
        competitionStats,
        inventory,
        achievements,
        tasks,
        habits,
        goals
      ] = await Promise.allSettled([
        adminApi.getUser(userId),
        adminApi.getUserCharacter(userId).catch(() => null),
        adminApi.getUserHabitStats(userId).catch(() => null),
        adminApi.getUserTaskStats(userId).catch(() => null),
        adminApi.getUserEventStats(userId).catch(() => null),
        adminApi.getUserAchievementStats(userId).catch(() => null),
        adminApi.getUserCompetitionStats(userId).catch(() => null),
        adminApi.getUserInventory(userId).catch(() => null),
        adminApi.getUserAchievements(userId).catch(() => null),
        adminApi.getUserTasks(userId).catch(() => null),
        adminApi.getUserHabits(userId).catch(() => null),
        adminApi.getUserGoals(userId).catch(() => null)
      ]);

      setData({
        user: user.status === 'fulfilled' ? user.value : null,
        character: character.status === 'fulfilled' ? character.value : null,
        habitStats: habitStats.status === 'fulfilled' ? habitStats.value : null,
        taskStats: taskStats.status === 'fulfilled' ? taskStats.value : null,
        eventStats: eventStats.status === 'fulfilled' ? eventStats.value : null,
        achievementStats: achievementStats.status === 'fulfilled' ? achievementStats.value : null,
        competitionStats: competitionStats.status === 'fulfilled' ? competitionStats.value : null,
        inventory: inventory.status === 'fulfilled' ? inventory.value : null,
        achievements: achievements.status === 'fulfilled' ? achievements.value : null,
        tasks: tasks.status === 'fulfilled' ? tasks.value : null,
        habits: habits.status === 'fulfilled' ? habits.value : null,
        goals: goals.status === 'fulfilled' ? goals.value : null
      });
    } catch (err) {
      setError(err.message ?? 'Не удалось загрузить данные пользователя');
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return '—';
    try {
      const date = new Date(dateString);
      if (isNaN(date.getTime())) return '—';
      return date.toLocaleString('ru-RU', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
      });
    } catch (e) {
      return String(dateString);
    }
  };

  const exportToPDF = () => {
    if (!data || !data.user) {
      setNotification({
        isOpen: true,
        message: 'Нет данных для экспорта',
        type: 'warning',
        title: 'Предупреждение'
      });
      return;
    }

    try {
      exportUserToPDF(data, formatDate);
      setNotification({
        isOpen: true,
        message: 'PDF файл успешно создан и загружен',
        type: 'success',
        title: 'Успешно'
      });
    } catch (error) {
      console.error('Ошибка генерации PDF:', error);
      setNotification({
        isOpen: true,
        message: `Ошибка при генерации PDF: ${error.message}`,
        type: 'error',
        title: 'Ошибка'
      });
    }
  };

  if (!isOpen) return null;

  const rarityLabel = (rarity) => labelFor(RARITY_LABELS, rarity, 'Другая');

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="lg"
      title={`Пользователь #${userId}`}
      footer={
        data ? (
          <div className="admin-modal-actions">
            <Button
              variant="secondary"
              icon={<FileDown size={16} aria-hidden="true" />}
              onClick={exportToPDF}
              disabled={!data || loading}
            >
              Экспорт в PDF
            </Button>
            <Button onClick={onClose}>Закрыть</Button>
          </div>
        ) : null
      }
    >
      <div className="admin-modal">
        {loading ? (
          <StateView state="loading" message="Загрузка данных…" compact />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить данные" message={error} onRetry={loadUserData} compact />
        ) : data ? (
          <>
            {/* Основная информация о пользователе */}
            <StatCard title="Основная информация">
              <StatRow label="ID" value={data.user?.id ?? '—'} />
              <StatRow label="Имя пользователя" value={data.user?.username ?? '—'} />
              <StatRow label="Эл. почта" value={data.user?.email ?? '—'} />
              <StatRow label="Роль" value={labelFor(ROLE_LABELS, data.user?.role ?? 'student', 'Другая роль')} />
              <StatRow label="Монеты" value={<StatValue kind="coins" value={data.user?.coins ?? 0} />} />
              <StatRow label="Дата создания" value={formatDate(data.user?.created_at)} />
            </StatCard>

            {/* Информация о персонаже */}
            {data.character && (
              <StatCard title="Персонаж">
                <StatRow label="Имя" value={data.character.name ?? '—'} />
                <StatRow label="Уровень" value={data.character.level ?? 0} />
                <StatRow label="Уровень интеллекта" value={data.character.intelligence_level ?? 0} />
                <StatRow label="Очки интеллекта" value={<StatValue kind="intelligence" value={data.character.intelligence_points ?? 0} />} />
                <StatRow label="Рейтинг" value={data.character.rating ?? 0} />
                <StatRow label="Настроение" value={`${data.character.satisfaction ?? 0}%`} />
                <StatRow label="Бонусные очки" value={data.character.bonus_points ?? 0} />
                <StatRow label="Дата создания" value={formatDate(data.character.created_at)} />
              </StatCard>
            )}

            {/* Статистика по привычкам */}
            {data.habitStats && (
              <StatCard title="Привычки">
                <StatRow label="Всего привычек" value={data.habitStats.total_habits ?? 0} />
                <StatRow label="Всего выполнений" value={data.habitStats.total_completions ?? 0} />
                {data.habitStats.by_frequency && (
                  <>
                    <StatRow label="Ежедневные" value={data.habitStats.by_frequency.daily ?? 0} />
                    <StatRow label="Еженедельные" value={data.habitStats.by_frequency.weekly ?? 0} />
                    <StatRow label="Ежемесячные" value={data.habitStats.by_frequency.monthly ?? 0} />
                  </>
                )}
                {data.habitStats.habits && data.habitStats.habits.length > 0 && (
                  <div className="admin-detail-list">
                    {data.habitStats.habits.map((habit, idx) => (
                      <StatRow key={idx} label={habit.name} value={`${habit.completions} выполн.`} />
                    ))}
                  </div>
                )}
              </StatCard>
            )}

            {/* Статистика по задачам */}
            {data.taskStats && (
              <StatCard title="Задачи">
                <StatRow label="Всего задач" value={data.taskStats.total ?? 0} />
                <StatRow label="Выполнено" value={data.taskStats.completed ?? 0} />
                <StatRow label="В процессе" value={data.taskStats.in_progress ?? 0} />
                <StatRow label="К выполнению" value={data.taskStats.todo ?? 0} />
                <StatRow label="Отменено" value={data.taskStats.cancelled ?? 0} />
                <StatRow label="Процент выполнения" value={`${data.taskStats.completion_rate ?? 0}%`} />
                {data.taskStats.by_priority && (
                  <>
                    <StatRow label="Низкий приоритет" value={data.taskStats.by_priority.low ?? 0} />
                    <StatRow label="Средний приоритет" value={data.taskStats.by_priority.medium ?? 0} />
                    <StatRow label="Высокий приоритет" value={data.taskStats.by_priority.high ?? 0} />
                    <StatRow label="Срочный приоритет" value={data.taskStats.by_priority.urgent ?? 0} />
                  </>
                )}
              </StatCard>
            )}

            {/* Статистика по событиям */}
            {data.eventStats && (
              <StatCard title="События">
                <StatRow label="Зарегистрировано" value={data.eventStats.registered_events ?? 0} />
                <StatRow label="Посещено" value={data.eventStats.attended_events ?? 0} />
                <StatRow label="Процент посещаемости" value={`${data.eventStats.attendance_rate ?? 0}%`} />
              </StatCard>
            )}

            {/* Статистика по достижениям */}
            {data.achievementStats && (
              <StatCard title="Достижения">
                <StatRow label="Всего достижений" value={data.achievementStats.total_achievements ?? 0} />
                <StatRow label="Получено" value={data.achievementStats.completed ?? 0} />
                <StatRow label="В процессе" value={data.achievementStats.in_progress ?? 0} />
                <StatRow label="Процент получения" value={`${data.achievementStats.completion_rate ?? 0}%`} />
              </StatCard>
            )}

            {/* Статистика по соревнованиям */}
            {data.competitionStats && (
              <StatCard title="Соревнования">
                <StatRow label="Всего соревнований" value={data.competitionStats.total_competitions ?? 0} />
                <StatRow label="Завершено" value={data.competitionStats.completed_competitions ?? 0} />
                <StatRow label="Первые места" value={data.competitionStats.first_places ?? 0} />
                <StatRow label="Вторые места" value={data.competitionStats.second_places ?? 0} />
                <StatRow label="Третьи места" value={data.competitionStats.third_places ?? 0} />
                {data.competitionStats.total_competitions > 0 && (
                  <StatRow
                    label="Процент побед"
                    value={`${Math.round(((data.competitionStats.first_places ?? 0) / data.competitionStats.total_competitions) * 100)}%`}
                  />
                )}
              </StatCard>
            )}

            {/* Инвентарь */}
            <StatCard title="Инвентарь">
              {data.inventory && Array.isArray(data.inventory) ? (
                <>
                  <StatRow label="Всего предметов" value={data.inventory.length} />
                  {data.inventory.length > 0 ? (
                    <div className="admin-modal-table-wrap admin-detail-list">
                      <table className="admin-modal-table">
                        <thead>
                          <tr>
                            <th>Предмет</th>
                            <th className="num">Количество</th>
                            <th>Редкость</th>
                          </tr>
                        </thead>
                        <tbody>
                          {data.inventory.map((userItem, idx) => {
                            const item = userItem.item || userItem;
                            const itemName = item?.name ?? userItem.item_name ?? item?.item_name ?? 'Неизвестный предмет';
                            const quantity = userItem.quantity ?? 0;
                            const rarity = item?.rarity ?? userItem.rarity ?? 'common';
                            return (
                              <tr key={userItem.id || userItem.item_id || idx}>
                                <td>{itemName}</td>
                                <td className="num">{quantity}</td>
                                <td>{rarityLabel(rarity)}</td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <div className="admin-empty-note">Инвентарь пуст</div>
                  )}
                </>
              ) : (
                <div className="admin-empty-note">
                  {data.inventory === null ? 'Данные не загружены' : 'Нет данных об инвентаре'}
                </div>
              )}
            </StatCard>

            {/* Достижения */}
            {data.achievements && Array.isArray(data.achievements) && (
              <StatCard title="Список достижений">
                <StatRow label="Всего" value={data.achievements.length} />
                {data.achievements.length > 0 && (
                  <div className="admin-detail-list">
                    {data.achievements.slice(0, 20).map((ach, idx) => {
                      const achievement = ach.achievement || ach;
                      return (
                        <DetailsItem
                          key={ach.id || idx}
                          title={achievement?.name ?? ach.achievement_name ?? '—'}
                          description={achievement?.description ?? ach.description}
                          status={ach.completed ? 'Получено' : 'В процессе'}
                          progress={
                            ach.progress !== undefined
                              ? `${ach.progress} / ${ach.requirement_value ?? achievement?.requirement_value ?? '—'}`
                              : null
                          }
                          completed={ach.completed}
                        />
                      );
                    })}
                    {data.achievements.length > 20 && (
                      <div className="admin-detail-item__meta">И ещё {data.achievements.length - 20} достижений…</div>
                    )}
                  </div>
                )}
              </StatCard>
            )}

            {/* Задачи */}
            {data.tasks && Array.isArray(data.tasks) && (
              <StatCard title="Список задач">
                <StatRow label="Всего" value={data.tasks.length} />
                {data.tasks.length > 0 && (
                  <div className="admin-detail-list">
                    {data.tasks.slice(0, 20).map((task, idx) => (
                      <DetailsItem
                        key={task.id || idx}
                        title={task.title ?? '—'}
                        description={task.description}
                        status={labelFor(TASK_STATUS_LABELS, task.status, 'Другой статус')}
                        completed={task.status === 'completed'}
                        metadata={`Приоритет: ${labelFor(TASK_PRIORITY_LABELS, task.priority, 'другой')}, срок: ${formatDate(task.due_date)}`}
                      />
                    ))}
                    {data.tasks.length > 20 && (
                      <div className="admin-detail-item__meta">И ещё {data.tasks.length - 20} задач…</div>
                    )}
                  </div>
                )}
              </StatCard>
            )}

            {/* Привычки */}
            {data.habits && Array.isArray(data.habits) && (
              <StatCard title="Список привычек">
                <StatRow label="Всего" value={data.habits.length} />
                {data.habits.length > 0 && (
                  <div className="admin-detail-list">
                    {data.habits.slice(0, 20).map((habit, idx) => (
                      <DetailsItem
                        key={habit.id || idx}
                        title={habit.name ?? '—'}
                        description={habit.description}
                        status={`Частота: ${labelFor(HABIT_FREQUENCY_LABELS, habit.frequency, 'другая')}`}
                        metadata={`Создано: ${formatDate(habit.created_at)}`}
                      />
                    ))}
                    {data.habits.length > 20 && (
                      <div className="admin-detail-item__meta">И ещё {data.habits.length - 20} привычек…</div>
                    )}
                  </div>
                )}
              </StatCard>
            )}

            {/* Цели */}
            {data.goals && Array.isArray(data.goals) && (
              <StatCard title="Список целей">
                <StatRow label="Всего" value={data.goals.length} />
                {data.goals.length > 0 && (
                  <div className="admin-detail-list">
                    {data.goals.slice(0, 20).map((goal, idx) => (
                      <DetailsItem
                        key={goal.id || idx}
                        title={goal.title ?? '—'}
                        description={goal.description}
                        status={labelFor(GOAL_STATUS_LABELS, goal.status, 'Другой статус')}
                        completed={goal.status === 'completed'}
                        metadata={`Срок: ${formatDate(goal.deadline)}, задач: ${goal.tasks?.length ?? 0}`}
                      />
                    ))}
                    {data.goals.length > 20 && (
                      <div className="admin-detail-item__meta">И ещё {data.goals.length - 20} целей…</div>
                    )}
                  </div>
                )}
              </StatCard>
            )}
          </>
        ) : null}
      </div>
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
    </Modal>
  );
}

function StatCard({ title, children }) {
  return (
    <div className="admin-detail-card">
      <h3 className="admin-detail-card__title">{title}</h3>
      {children}
    </div>
  );
}

function StatRow({ label, value }) {
  return (
    <div className="admin-detail-row">
      <span className="admin-detail-row__label">{label}</span>
      <span className="admin-detail-row__value">{value}</span>
    </div>
  );
}

function DetailsItem({ title, description, status, progress, completed, metadata }) {
  const [expanded, setExpanded] = useState(false);
  const Chevron = expanded ? ChevronDown : ChevronRight;
  return (
    <div className={`admin-detail-item ${completed ? 'admin-detail-item--done' : ''}`}>
      <button
        type="button"
        className="admin-detail-item__head"
        onClick={() => setExpanded((value) => !value)}
        disabled={!description}
        aria-expanded={description ? expanded : undefined}
      >
        <span>{title}</span>
        {description ? <Chevron size={16} aria-hidden="true" /> : null}
      </button>
      {status ? (
        <div className={`admin-detail-item__meta ${completed ? 'admin-detail-item__meta--done' : ''}`}>{status}</div>
      ) : null}
      {progress ? <div className="admin-detail-item__meta">Прогресс: {progress}</div> : null}
      {metadata ? <div className="admin-detail-item__meta">{metadata}</div> : null}
      {expanded && description ? <div className="admin-detail-item__desc">{description}</div> : null}
    </div>
  );
}
