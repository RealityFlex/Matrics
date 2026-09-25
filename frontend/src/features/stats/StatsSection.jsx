import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import { getUserStatistics } from '../../services/stats.js';
import { StatsSummaryCard } from './components/StatsSummaryCard.jsx';
import { Backpack, BarChart3, CalendarCheck, Flag, ListChecks, Repeat, TrendingUp } from 'lucide-react';
import { StateView } from '../../components/ui/index.jsx';
import { StatIcon } from '../../components/ui/icons.jsx';

const lucide = (Icon) => <Icon size={20} aria-hidden="true" />;

function formatValue(value, fallback = '—') {
  if (value === null || value === undefined) {
    return fallback;
  }
  if (typeof value === 'number') {
    return value;
  }
  return String(value);
}

export function StatsSection({ isActive }) {
  const { user } = useAppState();

  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadStats = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const data = await getUserStatistics(user.id);
      setStats(data);
    } catch (loadError) {
      console.error('Ошибка загрузки статуса:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить статистику');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (isActive && user?.id) {
      loadStats();
    }
  }, [isActive, user?.id]); // Убрали loadStats из зависимостей

  const summaryCards = useMemo(() => {
    if (!stats) {
      return [];
    }
    const cards = [];
    if (stats.character && !stats.character.error) {
      cards.push({
        title: 'Настроение',
        value: formatValue(stats.character.satisfaction, 0),
        subtitle: 'Из 100',
        icon: <StatIcon kind="satisfaction" size={20} />
      });
      cards.push({
        title: 'Монеты',
        value: formatValue(stats.character.coins, 0),
        subtitle: 'На счету',
        icon: <StatIcon kind="coins" size={20} />
      });
      cards.push({
        title: 'Рейтинг',
        value: formatValue(stats.character.rating, 0),
        subtitle: 'Очки рейтинга',
        icon: <StatIcon kind="rating" size={20} />
      });
      if (stats.character.intelligence_level !== undefined) {
        cards.push({
          title: 'Уровень интеллекта',
          value: formatValue(stats.character.intelligence_level, 0),
          subtitle: `Очков: ${formatValue(stats.character.intelligence_points, 0)}`,
          icon: <StatIcon kind="intelligence" size={20} />
        });
      }
    }
    if (stats.tasks && !stats.tasks.error) {
      cards.push({
        title: 'Выполнено задач',
        value: formatValue(stats.tasks.completed, 0),
        subtitle: `Всего задач: ${formatValue(stats.tasks.total, 0)}`,
        icon: lucide(ListChecks)
      });
      if (stats.tasks.completion_rate !== undefined) {
        cards.push({
          title: 'Доля выполненных задач',
          value: `${formatValue(stats.tasks.completion_rate, 0)}%`,
          subtitle: 'От всех задач',
          icon: lucide(TrendingUp)
        });
      }
    }
    if (stats.habits && !stats.habits.error) {
      cards.push({
        title: 'Отметок привычек',
        value: formatValue(stats.habits.total_completions, 0),
        subtitle: `Всего привычек: ${formatValue(stats.habits.total_habits, 0)}`,
        icon: lucide(Repeat)
      });
    }
    if (stats.inventory && !stats.inventory.error) {
      cards.push({
        title: 'Предметов в инвентаре',
        value: formatValue(stats.inventory.total_items, 0),
        subtitle: 'Всего предметов',
        icon: lucide(Backpack)
      });
    }
    if (stats.achievements && !stats.achievements.error) {
      cards.push({
        title: 'Получено достижений',
        value: formatValue(stats.achievements.completed, 0),
        subtitle: `Всего: ${formatValue(stats.achievements.total_achievements, 0)}`,
        icon: <StatIcon kind="achievement" size={20} />
      });
    }
    if (stats.events && !stats.events.error) {
      cards.push({
        title: 'Посещено событий',
        value: formatValue(stats.events.attended_events, 0),
        subtitle: `Зарегистрировано: ${formatValue(stats.events.registered_events, 0)}`,
        icon: lucide(CalendarCheck)
      });
    }
    if (stats.competitions && !stats.competitions.error) {
      cards.push({
        title: 'Соревнования',
        value: formatValue(stats.competitions.completed_competitions, 0),
        subtitle: `Завершено · участий: ${formatValue(stats.competitions.total_competitions, 0)}, побед: ${formatValue(stats.competitions.first_places, 0)}`,
        icon: lucide(Flag)
      });
    }
    return cards;
  }, [stats]);

  const header = (
    <div className="section-header">
      <h2 className="inline-icon">
        <BarChart3 size={22} aria-hidden="true" /> Статистика
      </h2>
    </div>
  );

  if (isLoading) {
    return (
      <div>
        {header}
        <StateView state="loading" message="Загружаем статистику…" />
      </div>
    );
  }

  if (error) {
    return (
      <div>
        {header}
        <StateView state="error" title="Не удалось загрузить статистику" message={error} onRetry={loadStats} />
      </div>
    );
  }

  if (!stats) {
    return (
      <div>
        {header}
        <StateView state="empty" title="Статистики пока нет" message="Она появится после первых действий в приложении." />
      </div>
    );
  }

  return (
    <div>
      {header}
      <div className="stats-grid" id="statsContent">
        {summaryCards.map((card, index) => (
          <StatsSummaryCard
            key={`${card.title}-${index}`}
            title={card.title}
            value={card.value}
            subtitle={card.subtitle}
            icon={card.icon}
          />
        ))}
      </div>
    </div>
  );
}

