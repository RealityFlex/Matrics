import React, { useCallback, useEffect, useState } from 'react';
import { Footprints, Heart, Play, Trophy } from 'lucide-react';
import { Badge, Button, Card, Skeleton } from '../../components/ui/index.jsx';
import { StatIcon } from '../../components/ui/icons.jsx';
import { getGameOverview } from '../../services/game.js';
import { useAppDispatch, useAppState } from '../../state/AppProvider.jsx';
import { useRefreshUserAndCharacter } from '../../hooks/useRefreshUserAndCharacter.js';
import { toast } from '../../components/ui/toast.jsx';
import { RunnerGame } from './RunnerGame.jsx';
import { formatNextLife, livesOf } from './lives.js';
import '../../styles/game.css';

/**
 * Карточка мини-игры на главном экране: рекорд, место в группе, жизни и запуск забега.
 */
export function GameCard({ isActive }) {
  const { user, pendingGame, character } = useAppState();
  const dispatch = useAppDispatch();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();
  const [overview, setOverview] = useState(null);
  const [state, setState] = useState('loading');
  const [open, setOpen] = useState(false);
  const [, setTick] = useState(0);

  const load = useCallback(async () => {
    if (!user?.id) return;
    try {
      const data = await getGameOverview(user.id);
      setOverview(data);
      setState('ready');
    } catch {
      setState((prev) => (prev === 'ready' ? prev : 'error'));
    }
  }, [user?.id]);

  useEffect(() => {
    if (isActive) load();
  }, [isActive, load]);

  useEffect(() => {
    if (!isActive || !overview?.next_life_at) return undefined;
    const timer = window.setInterval(() => {
      if (new Date(overview.next_life_at).getTime() <= Date.now()) load();
      else setTick((n) => n + 1);
    }, 15000);
    return () => window.clearInterval(timer);
  }, [isActive, overview?.next_life_at, load]);

  const lives = livesOf(overview);
  const canPlay = Boolean(user?.id) && lives.current > 0;

  useEffect(() => {
    if (!pendingGame || !user?.id || state !== 'ready') return;
    dispatch({ type: 'SET_PENDING_GAME', value: false });
    if (lives.current > 0) {
      setOpen(true);
      return;
    }
    toast.info('Пока нет попыток', 'Выполните задачу, получите достижение или дождитесь восстановления жизни.');
  }, [pendingGame, user?.id, dispatch, lives.current, state]);

  const handleFinished = useCallback(
    (result) => {
      if (result.coins_awarded > 0) {
        refreshUserAndCharacter?.().catch(() => {});
      }
      load();
    },
    [load, refreshUserAndCharacter]
  );

  const prize = overview?.last_week_prize;
  useEffect(() => {
    if (!prize) return;
    const key = `game-prize-${prize.week_start}`;
    try {
      if (sessionStorage.getItem(key)) return;
      sessionStorage.setItem(key, '1');
    } catch {
      /* без sessionStorage просто покажем тост ещё раз */
    }
    toast.success(`${prize.place} место в забеге прошлой недели`, `+${prize.coins} монет на счету`);
  }, [prize]);

  const week = overview?.week;
  const prizes = overview?.weekly_prizes ?? [];
  const nextLife = formatNextLife(overview?.next_life_at);

  return (
    <Card className="game-card">
      <div className="game-card__head">
        <span className="game-card__icon" aria-hidden="true">
          <Footprints size={22} />
        </span>
        <div className="game-card__titles">
          <h3 className="game-card__title">Забег до пары</h3>
          <p className="game-card__subtitle">
            {overview?.group_name ? `Соревнование недели · ${overview.group_name}` : 'Соревнование недели'}
          </p>
        </div>
        <Badge tone="info">Мини-игра</Badge>
      </div>

      {state === 'loading' ? (
        <div className="game-card__skeleton">
          <Skeleton height={14} width="70%" />
          <Skeleton height={14} width="50%" />
        </div>
      ) : null}

      {state === 'error' ? (
        <p className="game-card__muted">Рейтинг сейчас недоступен. Попробуйте обновить экран.</p>
      ) : null}

      {state === 'ready' && overview ? (
        <>
          <div className="game-card__stats">
            <div className="game-card__stat">
              <span className="game-card__stat-value tabular">{week?.best || '—'}</span>
              <span className="game-card__stat-label">рекорд недели</span>
            </div>
            <div className="game-card__stat">
              <span className="game-card__stat-value tabular">{week?.rank ? `${week.rank}/${overview.players}` : '—'}</span>
              <span className="game-card__stat-label">место</span>
            </div>
            <div className="game-card__stat">
              <span className="game-card__lives" aria-label={`Жизни ${lives.current} из ${lives.max}`}>
                {Array.from({ length: lives.max }, (_, index) => (
                  <Heart
                    key={index}
                    size={16}
                    fill={index < lives.current ? 'currentColor' : 'none'}
                    className={index < lives.current ? 'game-card__heart is-full' : 'game-card__heart'}
                  />
                ))}
              </span>
              <span className="game-card__stat-label">
                {lives.current > 0 ? 'попытки' : nextLife ? `ещё ${nextLife}` : 'нет попыток'}
              </span>
            </div>
          </div>

          {lives.current === 0 ? (
            <p className="game-card__muted">
              Забег открывается за учёбу: выполните задачу, отметьтесь на паре или получите достижение.
              {nextLife ? ` Следующая жизнь через ${nextLife}.` : ''}
            </p>
          ) : null}

          {overview.top?.length ? (
            <ol className="game-card__top">
              {overview.top.slice(0, 3).map((entry) => (
                <li key={entry.user_id} className={entry.is_me ? 'is-me' : ''}>
                  <span className={`game-board__rank game-board__rank--${entry.rank}`}>{entry.rank}</span>
                  <span className="game-card__top-name">{entry.is_me ? 'Вы' : entry.name}</span>
                  <span className="tabular">{entry.score}</span>
                </li>
              ))}
            </ol>
          ) : (
            <p className="game-card__muted">На этой неделе ещё никто не бегал — займите первое место.</p>
          )}

          {prizes.length ? (
            <p className="game-card__prizes">
              <Trophy size={14} aria-hidden="true" className="stat-tone--coins" />
              Призы недели:
              {prizes.map((coins, index) => (
                <span key={index} className="game-card__prize">
                  {index + 1} место — <StatIcon kind="coins" size={12} /> {coins}
                </span>
              ))}
            </p>
          ) : null}
        </>
      ) : null}

      <Button block icon={<Play size={18} />} onClick={() => setOpen(true)} disabled={!canPlay || state === 'loading'}>
        {state === 'loading' ? 'Загружаем…' : canPlay ? 'Играть' : 'Нет попыток'}
      </Button>

      <RunnerGame
        isOpen={open}
        onClose={() => {
          setOpen(false);
          load();
        }}
        userId={user?.id}
        overview={overview}
        onFinished={handleFinished}
        characterKey={character?.active_character_set?.asset_key}
      />
    </Card>
  );
}
