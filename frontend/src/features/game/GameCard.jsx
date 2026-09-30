import React, { useCallback, useEffect, useState } from 'react';
import { Footprints, Play, Trophy } from 'lucide-react';
import { Badge, Button, Card, Skeleton } from '../../components/ui/index.jsx';
import { StatIcon } from '../../components/ui/icons.jsx';
import { getGameOverview } from '../../services/game.js';
import { useAppDispatch, useAppState } from '../../state/AppProvider.jsx';
import { useRefreshUserAndCharacter } from '../../hooks/useRefreshUserAndCharacter.js';
import { toast } from '../../components/ui/toast.jsx';
import { RunnerGame } from './RunnerGame.jsx';
import '../../styles/game.css';

/**
 * Карточка мини-игры на главном экране: рекорд, место в группе, топ недели и запуск забега.
 */
export function GameCard({ isActive }) {
  const { user, pendingGame, character } = useAppState();
  const dispatch = useAppDispatch();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();
  const [overview, setOverview] = useState(null);
  const [state, setState] = useState('loading');
  const [open, setOpen] = useState(false);

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

  // Диплинк ?startapp=game (кнопка «Играть» из бота)
  useEffect(() => {
    if (pendingGame && user?.id) {
      setOpen(true);
      dispatch({ type: 'SET_PENDING_GAME', value: false });
    }
  }, [pendingGame, user?.id, dispatch]);

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
        <p className="game-card__muted">Рейтинг сейчас недоступен — играть всё равно можно.</p>
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
              <span className="game-card__stat-value tabular">
                {overview.rewarded_runs_left}/{overview.rewarded_runs_total}
              </span>
              <span className="game-card__stat-label">забегов с наградой</span>
            </div>
          </div>

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

      <Button block icon={<Play size={18} />} onClick={() => setOpen(true)} disabled={!user?.id}>
        Играть
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
