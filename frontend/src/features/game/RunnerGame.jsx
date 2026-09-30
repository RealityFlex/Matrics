import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import {
  ArrowDown,
  ArrowLeftRight,
  ArrowUp,
  Crown,
  Pause,
  Play,
  RotateCcw,
  Trophy,
  X
} from 'lucide-react';
import { Badge, Button, Spinner, StateView } from '../../components/ui/index.jsx';
import { StatIcon, StatValue } from '../../components/ui/icons.jsx';
import { abandonGameRun, finishGameRun, getGameLeaderboard, startGameRun } from '../../services/game.js';
import { haptic, maxBackButton } from '../../utils/maxBridge.js';
import { RunnerEngine } from './runnerEngine.js';
import { formatNextLife, livesOf } from './lives.js';

function Leaderboard({ userId }) {
  const [scope, setScope] = useState('group');
  const [data, setData] = useState(null);
  const [state, setState] = useState('loading');

  const load = useCallback(async () => {
    setState('loading');
    try {
      setData(await getGameLeaderboard(userId, scope));
      setState('ready');
    } catch {
      setState('error');
    }
  }, [userId, scope]);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="game-board">
      <div className="game-board__tabs" role="tablist">
        {[
          ['group', 'Моя группа'],
          ['all', 'Все игроки']
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={scope === id}
            className={`game-board__tab ${scope === id ? 'is-active' : ''}`}
            onClick={() => setScope(id)}
          >
            {label}
          </button>
        ))}
      </div>
      {state === 'loading' ? <StateView state="loading" compact /> : null}
      {state === 'error' ? <StateView state="error" title="Рейтинг недоступен" onRetry={load} compact /> : null}
      {state === 'ready' && data ? (
        data.entries.length ? (
          <>
            <p className="game-board__caption">
              {data.scope === 'group' && data.group_name ? data.group_name : 'Все игроки'} · неделя с{' '}
              {new Date(data.week_start).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
            </p>
            <ol className="game-board__list">
              {data.entries.map((entry) => (
                <li key={entry.user_id} className={`game-board__row ${entry.is_me ? 'is-me' : ''}`}>
                  <span className={`game-board__rank game-board__rank--${entry.rank}`}>{entry.rank}</span>
                  <span className="game-board__name">{entry.is_me ? `${entry.name} (вы)` : entry.name}</span>
                  <span className="game-board__score tabular">{entry.score}</span>
                </li>
              ))}
            </ol>
            {data.me && !data.entries.some((entry) => entry.is_me) ? (
              <p className="game-board__caption">Ваше место: {data.me.rank} · {data.me.score} очков</p>
            ) : null}
          </>
        ) : (
          <StateView state="empty" title="На этой неделе ещё никто не бегал" message="Станьте первым в рейтинге." compact />
        )
      ) : null}
    </div>
  );
}

/**
 * Полноэкранная мини-игра «Забег до пары».
 * Фазы: intro → countdown → running ⇄ paused → submitting → result (+ leaderboard).
 */
export function RunnerGame({ isOpen, onClose, userId, overview, onFinished, characterKey }) {
  const stageRef = useRef(null);
  const engineRef = useRef(null);
  const runRef = useRef(null);
  const finishingRef = useRef(false);
  const [phase, setPhase] = useState('intro');
  const [ready, setReady] = useState(false);
  const [hud, setHud] = useState({ score: 0, coins: 0, distance: 0 });
  const [countdown, setCountdown] = useState(3);
  const [error, setError] = useState(null);
  const [localResult, setLocalResult] = useState(null);
  const [serverResult, setServerResult] = useState(null);
  const [showBoard, setShowBoard] = useState(false);
  const [rewarded, setRewarded] = useState(true);

  const submit = useCallback(
    async (result) => {
      const run = runRef.current;
      setLocalResult(result);
      if (!run) {
        setPhase('result');
        return;
      }
      finishingRef.current = true;
      setPhase('submitting');
      setError(null);
      try {
        const response = await finishGameRun(userId, run.run_id, result);
        runRef.current = null;
        setServerResult(response);
        if (response.new_record) haptic('success');
        onFinished?.(response);
      } catch (submitError) {
        setError(submitError?.message ?? 'Не удалось сохранить результат');
      } finally {
        finishingRef.current = false;
        setPhase('result');
      }
    },
    [userId, onFinished]
  );

  // Движок живёт, пока открыт экран игры
  useEffect(() => {
    if (!isOpen || !stageRef.current) return undefined;
    const engine = new RunnerEngine(stageRef.current, {
      onReady: () => setReady(true),
      onHud: (value) => setHud(value),
      onCrash: (result) => {
        haptic('error');
        submit(result);
      },
      onAutoPause: () => setPhase('paused')
    }, { characterKey });
    engineRef.current = engine;
    setPhase('intro');
    setServerResult(null);
    setLocalResult(null);
    setShowBoard(false);
    return () => {
      engine.dispose();
      engineRef.current = null;
      setReady(false);
      const run = runRef.current;
      runRef.current = null;
      if (run?.run_id && !finishingRef.current) {
        abandonGameRun(userId, run.run_id).catch(() => {});
      }
    };
    // submit стабилен в пределах открытия экрана
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen]);

  const startRun = useCallback(async () => {
    const engine = engineRef.current;
    if (!engine) return;
    setError(null);
    setServerResult(null);
    setLocalResult(null);
    setShowBoard(false);
    setPhase('starting');
    try {
      const run = await startGameRun(userId);
      runRef.current = run;
      setRewarded(run.rewarded);
      engine.reset(run.seed);
    } catch (startError) {
      setError(startError?.message ?? 'Не удалось начать забег');
      setPhase('intro');
      return;
    }
    engine.setCountdown();
    setPhase('countdown');
    setCountdown(3);
  }, [userId]);

  useEffect(() => {
    if (phase !== 'countdown') return undefined;
    if (countdown <= 0) {
      engineRef.current?.start();
      setPhase('running');
      return undefined;
    }
    const timer = setTimeout(() => setCountdown((value) => value - 1), 650);
    return () => clearTimeout(timer);
  }, [phase, countdown]);

  const pause = useCallback(() => {
    engineRef.current?.pause();
    setPhase('paused');
  }, []);

  const resume = useCallback(() => {
    engineRef.current?.resume();
    setPhase('running');
  }, []);

  const requestClose = useCallback(() => {
    if (phase === 'running') {
      pause();
      return;
    }
    onClose();
  }, [phase, pause, onClose]);

  // Системная «Назад» в MAX и Esc: во время забега — пауза, иначе закрыть
  useEffect(() => {
    if (!isOpen) return undefined;
    const release = maxBackButton.push(requestClose);
    const onKey = (event) => {
      if (event.key === 'Escape') requestClose();
    };
    window.addEventListener('keydown', onKey);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      release();
      window.removeEventListener('keydown', onKey);
      document.body.style.overflow = previousOverflow;
    };
  }, [isOpen, requestClose]);

  if (!isOpen) return null;

  const lives = livesOf({ ...overview, lives: serverResult?.lives ?? overview?.lives, lives_max: serverResult?.lives_max ?? overview?.lives_max });
  const runsLeft = lives.current;
  const runsTotal = lives.max;
  const inGame = phase === 'running' || phase === 'paused' || phase === 'countdown';

  return createPortal(
    <div className="game-screen" role="dialog" aria-modal="true" aria-label="Мини-игра «Забег до пары»">
      <div ref={stageRef} className="game-stage" />

      <div className="game-topbar">
        {inGame ? (
          <div className="game-hud" aria-live="off">
            <span className="game-hud__score tabular">{hud.score}</span>
            <span className="game-hud__meta">
              <StatValue kind="coins" value={hud.coins} size={14} />
              <span className="tabular">{hud.distance} м</span>
              {!rewarded ? <Badge>без монет — дневной лимит</Badge> : null}
            </span>
          </div>
        ) : (
          <span />
        )}
        <div className="game-topbar__actions">
          {phase === 'running' ? (
            <button type="button" className="game-icon-btn" onClick={pause} aria-label="Пауза">
              <Pause size={20} />
            </button>
          ) : null}
          {phase !== 'running' ? (
            <button type="button" className="game-icon-btn" onClick={requestClose} aria-label="Закрыть игру">
              <X size={20} />
            </button>
          ) : null}
        </div>
      </div>

      {phase === 'countdown' ? (
        <div className="game-countdown" aria-live="assertive">
          {countdown > 0 ? countdown : 'Бежим!'}
        </div>
      ) : null}

      {phase === 'intro' || phase === 'starting' ? (
        <div className="game-sheet">
          <div className="game-sheet__head">
            <h2 className="game-sheet__title">Забег до пары</h2>
            <p className="game-sheet__lead">Одна жизнь — один забег. Жизни даются за задачи, пары и достижения и восстанавливаются сами.</p>
          </div>
          <ul className="game-rules">
            <li>
              <span className="game-rules__icon"><ArrowLeftRight size={18} /></span>
              Свайп влево/вправо — сменить полосу
            </li>
            <li>
              <span className="game-rules__icon"><ArrowUp size={18} /></span>
              Вверх — перепрыгнуть барьер
            </li>
            <li>
              <span className="game-rules__icon"><ArrowDown size={18} /></span>
              Вниз — проскользнуть под растяжкой
            </li>
          </ul>
          {overview ? (
            <div className="game-limits">
              <div>
                <b className="tabular">{runsLeft ?? 0}</b> из {runsTotal ?? 0} жизней
                <span className="game-limits__hint">
                  {runsLeft > 0
                    ? 'Забег тратит одну жизнь'
                    : formatNextLife(overview.next_life_at)
                      ? `Следующая жизнь через ${formatNextLife(overview.next_life_at)}`
                      : 'Выполните задачу или получите достижение'}
                </span>
              </div>
              <div className="game-limits__coins">
                <StatIcon kind="coins" size={16} />
                <span className="tabular">{overview.coins_today}/{overview.daily_coin_cap}</span>
              </div>
            </div>
          ) : null}
          {error ? <div className="inline-error" role="alert">{error}</div> : null}
          <div className="game-sheet__actions">
            <Button size="lg" block icon={<Play size={18} />} loading={phase === 'starting' || !ready} onClick={startRun} disabled={runsLeft <= 0}>
              {!ready ? 'Загружаем трассу…' : runsLeft > 0 ? 'Начать забег' : 'Нет попыток'}
            </Button>
            <Button variant="secondary" block icon={<Trophy size={16} />} onClick={() => setShowBoard((value) => !value)}>
              Рейтинг недели
            </Button>
          </div>
          {showBoard ? <Leaderboard userId={userId} /> : null}
          <p className="game-sheet__footnote">Клавиатура: стрелки или WASD, пробел — прыжок.</p>
        </div>
      ) : null}

      {phase === 'paused' ? (
        <div className="game-sheet game-sheet--center">
          <h2 className="game-sheet__title">Пауза</h2>
          <p className="game-sheet__lead tabular">{hud.score} очков · {hud.distance} м</p>
          <div className="game-sheet__actions">
            <Button size="lg" block icon={<Play size={18} />} onClick={resume}>
              Продолжить
            </Button>
            <Button variant="secondary" block onClick={() => engineRef.current?.finishNow()}>
              Завершить и засчитать
            </Button>
            <Button variant="ghost" block onClick={onClose}>
              Выйти без результата
            </Button>
          </div>
        </div>
      ) : null}

      {phase === 'submitting' ? (
        <div className="game-sheet game-sheet--center">
          <Spinner label="Сохраняем результат…" />
        </div>
      ) : null}

      {phase === 'result' ? (
        <div className="game-sheet">
          <div className="game-result">
            {serverResult?.new_record ? (
              <Badge tone="reward">
                <Crown size={14} aria-hidden="true" /> Новый рекорд
              </Badge>
            ) : null}
            <div className="game-result__score tabular">{serverResult?.score ?? localResult?.score ?? 0}</div>
            <div className="game-result__label">очков</div>
            <div className="game-result__stats">
              <span className="tabular">{serverResult?.distance ?? localResult?.distance ?? 0} м</span>
              <StatValue kind="coins" value={serverResult?.coins_collected ?? localResult?.coins ?? 0} size={14} />
              <span>собрано на трассе</span>
            </div>
          </div>

          {error ? (
            <div className="inline-error" role="alert">
              {error}
              {localResult && runRef.current ? (
                <Button size="sm" variant="secondary" icon={<RotateCcw size={14} />} onClick={() => submit(localResult)}>
                  Отправить ещё раз
                </Button>
              ) : null}
            </div>
          ) : null}

          {serverResult ? (
            <div className="game-outcome">
              {serverResult.coins_awarded > 0 ? (
                <div className="game-outcome__row game-outcome__row--reward">
                  <StatValue kind="coins" value={serverResult.coins_awarded} signed size={18} />
                  <span>начислено персонажу</span>
                </div>
              ) : (
                <div className="game-outcome__row">
                  {serverResult.coins_today >= serverResult.daily_coin_cap
                    ? 'Дневной лимит монет из игры набран — результат идёт в рейтинг.'
                    : 'Соберите больше монет на трассе — 10 штук дают 1 монету персонажу.'}
                </div>
              )}
              <div className="game-outcome__row">
                Осталось попыток: {runsLeft} из {runsTotal}
              </div>
              <div className="game-outcome__row">
                <Trophy size={16} aria-hidden="true" className="stat-tone--coins" />
                {serverResult.week.rank
                  ? `${serverResult.week.rank} место ${serverResult.scope === 'group' ? `в группе ${serverResult.group_name}` : 'среди всех игроков'} · игроков: ${serverResult.week.players}`
                  : 'Результат добавлен в рейтинг недели'}
              </div>
            </div>
          ) : null}

          <div className="game-sheet__actions">
            <Button size="lg" block icon={<RotateCcw size={18} />} onClick={startRun} disabled={runsLeft <= 0}>
              {runsLeft > 0 ? 'Ещё раз' : 'Нет попыток'}
            </Button>
            <Button variant="secondary" block icon={<Trophy size={16} />} onClick={() => setShowBoard((value) => !value)}>
              Рейтинг недели
            </Button>
            <Button variant="ghost" block onClick={onClose}>
              На главный экран
            </Button>
          </div>
          {showBoard ? <Leaderboard userId={userId} /> : null}
        </div>
      ) : null}
    </div>,
    document.body
  );
}
