import React, { useMemo, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import { useRefreshUserAndCharacter } from '../../hooks/useRefreshUserAndCharacter.js';
import { StatIcon } from '../ui/icons.jsx';

const clampPercent = (value) => Math.max(0, Math.min(100, value ?? 0));

export function AppHeader({ onLogout }) {
  const { user, character, activeSection } = useAppState();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const stats = useMemo(() => {
    const level = character?.intelligence_level ?? character?.level ?? 0;
    const rating = character?.rating != null ? Math.round(character.rating) : null;
    const coins = user?.coins ?? 0;
    const satisfaction = clampPercent(character?.satisfaction);
    const intelligencePoints = character?.intelligence_points ?? 0;
    const intelligenceProgress = clampPercent(intelligencePoints % 100);

    return {
      name: character?.name ?? user?.username ?? 'Без имени',
      level,
      rating,
      coins,
      satisfaction,
      intelligencePoints,
      intelligenceProgress
    };
  }, [user?.coins, user?.username, character]);

  const handleRefresh = async () => {
    if (typeof refreshUserAndCharacter !== 'function') {
      return;
    }
    setIsRefreshing(true);
    setError(null);
    try {
      await refreshUserAndCharacter();
    } catch (refreshError) {
      console.error('Ошибка обновления персонажа:', refreshError);
      setError(refreshError?.message ?? 'Не удалось обновить данные персонажа');
    } finally {
      setIsRefreshing(false);
    }
  };

  const intelligenceValue = `${stats.intelligencePoints % 100}/100`;

  return (
    <header className={`app-header ${activeSection === 'today' ? 'app-header--today' : ''}`} role="banner">
      <div className="app-header-row">
        <div className="app-header-stats">
          <div className="app-header-chip" title="Уровень интеллекта">
            <span className="chip-icon"><StatIcon kind="level" size={16} /></span>
            <span className="visually-hidden">Уровень интеллекта</span>
            <span className="chip-value">{stats.level ?? '—'}</span>
          </div>
          <div className="app-header-chip" title="Рейтинг">
            <span className="chip-icon"><StatIcon kind="rating" size={16} /></span>
            <span className="visually-hidden">Рейтинг</span>
            <span className="chip-value">{stats.rating ?? '—'}</span>
          </div>
          <div className="app-header-chip" title="Монеты">
            <span className="chip-icon"><StatIcon kind="coins" size={16} /></span>
            <span className="visually-hidden">Монеты</span>
            <span className="chip-value">{stats.coins}</span>
          </div>
        </div>
      </div>
      <div className="app-header-progress">
        <div className="metric-inline">
          <span className="metric-icon" title="Настроение"><StatIcon kind="satisfaction" size={16} /></span>
          <div className="metric-bar">
            <div className="metric-fill green" style={{ width: `${stats.satisfaction}%` }} />
          </div>
          <span className="metric-value">{stats.satisfaction}%</span>
        </div>
        <div className="metric-inline">
          <span className="metric-icon" title="Интеллект до следующего уровня"><StatIcon kind="intelligence" size={16} /></span>
          <div className="metric-bar">
            <div className="metric-fill blue" style={{ width: `${stats.intelligenceProgress}%` }} />
          </div>
          <span className="metric-value">{intelligenceValue}</span>
        </div>
      </div>
      {error ? <div className="app-header-error">{error}</div> : null}
    </header>
  );
}

