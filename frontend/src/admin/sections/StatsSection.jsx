import React, { useCallback, useEffect, useState } from 'react';
import { Award, CalendarDays, ListChecks, Package, Repeat, Store, Trophy, Users, UsersRound } from 'lucide-react';
import { adminApi } from '../api.js';
import { Button, StateView } from '../../components/ui/index.jsx';

export function StatsSection({ isActive }) {
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadStats = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.loadStats();
      setStats(data);
    } catch (loadError) {
      console.error('Ошибка загрузки статистики:', loadError);
      // Убеждаемся, что error всегда строка
      const errorMessage = loadError?.message || loadError?.toString() || 'Не удалось загрузить статистику';
      setError(typeof errorMessage === 'string' ? errorMessage : String(errorMessage));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadStats();
    }
  }, [isActive, loadStats]);

  const cards = stats
    ? [
        { key: 'users', Icon: Users, title: 'Пользователи', value: stats.users || stats.total_users || 0, hint: 'Всего зарегистрировано' },
        { key: 'items', Icon: Package, title: 'Предметы', value: stats.items ?? 0, hint: 'В системе' },
        { key: 'events', Icon: CalendarDays, title: 'События', value: stats.events ?? 0, hint: 'Создано событий' },
        { key: 'achievements', Icon: Award, title: 'Достижения', value: stats.achievements ?? 0, hint: 'Доступно достижений' },
        { key: 'shop', Icon: Store, title: 'Товары магазина', value: stats.shop ?? 0, hint: 'Товаров в продаже' },
        { key: 'competitions', Icon: Trophy, title: 'Соревнования', value: stats.competitions || stats.total_competitions || 0, hint: 'Всего соревнований' },
        { key: 'tasks', Icon: ListChecks, title: 'Задачи', value: stats.tasks || stats.total_tasks || 0, hint: 'Всего задач создано' },
        { key: 'habits', Icon: Repeat, title: 'Привычки', value: stats.habits || stats.total_habits || 0, hint: 'Всего привычек создано' },
        ...(stats.total_clans !== undefined && stats.total_clans !== null
          ? [{ key: 'clans', Icon: UsersRound, title: 'Кланы', value: stats.total_clans ?? 0, hint: 'Всего кланов' }]
          : [])
      ]
    : [];

  return (
    <section id="stats-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Статистика системы</h2>
        <Button size="sm" variant="secondary" onClick={loadStats} disabled={isLoading}>
          Обновить
        </Button>
      </div>
      {isLoading ? (
        <StateView state="loading" message="Загрузка статистики…" />
      ) : error ? (
        <StateView state="error" title="Не удалось загрузить статистику" message={error} onRetry={loadStats} />
      ) : stats ? (
        <div className="admin-stats-grid">
          {cards.map(({ key, Icon, title, value, hint }) => (
            <div key={key} className="admin-stat-card">
              <div className="admin-stat-card__label">
                <Icon size={16} aria-hidden="true" /> {title}
              </div>
              <div className="admin-stat-card__value">{value}</div>
              <div className="admin-stat-card__hint">{hint}</div>
            </div>
          ))}
        </div>
      ) : (
        <StateView state="empty" title="Нет данных" />
      )}
    </section>
  );
}
