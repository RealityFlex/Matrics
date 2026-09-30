import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CharacterViewer } from '../character/CharacterViewer.jsx';
import { CheckInCard } from './CheckInCard.jsx';
import { StreakCard } from './StreakCard.jsx';
import { WardrobeModal } from './WardrobeModal.jsx';
import { GameCard } from '../game/GameCard.jsx';
import { CalendarDays, LifeBuoy, Shirt } from 'lucide-react';
import { Button } from '../../components/ui/index.jsx';
import { RewardChips, StatIcon } from '../../components/ui/icons.jsx';
import { toast } from '../../components/ui/toast.jsx';
import { useAppDispatch, useAppState } from '../../state/AppProvider.jsx';
import { useDailyReward } from '../../hooks/useDailyReward.js';
import { useRefreshUserAndCharacter } from '../../hooks/useRefreshUserAndCharacter.js';
import { checkInLesson, getSchedule, getStreak, requestSupport } from '../../services/events.js';
import { joinByCode } from '../../services/users.js';
import { haptic, shareContent } from '../../utils/maxBridge.js';
import { loadAppConfig } from '../../utils/appConfig.js';
import { Card } from '../../components/ui/index.jsx';
import { livesRewardText } from '../game/lives.js';

const MOOD_LABELS = {
  ecstatic: 'в восторге',
  happy: 'доволен',
  neutral: 'спокоен',
  sad: 'грустит',
  depressed: 'подавлен'
};

function moodFromSatisfaction(value) {
  if (value >= 85) return 'ecstatic';
  if (value >= 65) return 'happy';
  if (value >= 40) return 'neutral';
  if (value >= 20) return 'sad';
  return 'depressed';
}

/**
 * «Сегодня» — первый экран и основной сценарий продукта:
 * отметка на паре → награда → реакция персонажа → уведомление в MAX.
 */
export function TodaySection({ isActive }) {
  const { user, character, pendingCheckIn } = useAppState();
  const dispatch = useAppDispatch();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();
  const viewerRef = useRef(null);

  const [schedule, setSchedule] = useState(null);
  const [scheduleState, setScheduleState] = useState('loading');
  const [streak, setStreak] = useState(null);
  const [streakState, setStreakState] = useState('loading');
  const [submitting, setSubmitting] = useState(false);
  const [checkInError, setCheckInError] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [burst, setBurst] = useState(null);
  const [wardrobeOpen, setWardrobeOpen] = useState(false);
  const [helpState, setHelpState] = useState('idle'); // idle | sending | sent | hidden

  useDailyReward({ autoFetch: true, silent: true });

  const loadSchedule = useCallback(async () => {
    if (!user?.id) return;
    setScheduleState('loading');
    try {
      setSchedule(await getSchedule(user.id));
      setScheduleState('ready');
    } catch {
      setScheduleState('error');
    }
  }, [user?.id]);

  const loadStreak = useCallback(async () => {
    if (!user?.id) return;
    try {
      setStreak(await getStreak(user.id));
      setStreakState('ready');
    } catch {
      setStreakState('error');
    }
  }, [user?.id]);

  useEffect(() => {
    if (isActive) {
      loadSchedule();
      loadStreak();
    }
  }, [isActive, loadSchedule, loadStreak]);

  // Отметка через чат-бота: обновляем карточку пары и серию без перезагрузки
  useEffect(() => {
    const handler = () => {
      loadSchedule();
      loadStreak();
    };
    window.addEventListener('matrix:attendance', handler);
    return () => window.removeEventListener('matrix:attendance', handler);
  }, [loadSchedule, loadStreak]);

  const submitCheckIn = useCallback(
    async (lessonId, code, method, localError) => {
      if (localError) {
        setCheckInError(localError);
        haptic('error');
        return;
      }
      if (!user?.id || !lessonId || !code) return;
      setSubmitting(true);
      setCheckInError(null);
      try {
        const result = await checkInLesson(lessonId, user.id, code, method);
        setLastResult(result);
        if (result.status === 'already') {
          toast.info('Вы уже отмечены', result.lesson?.name);
          return;
        }
        haptic('success');
        viewerRef.current?.playReaction();
        const rewards = result.rewards ?? {};
        setBurst({ id: Date.now(), ...rewards });
        window.setTimeout(() => setBurst(null), 2600);
        if (result.rewards_status === 'granted') {
          toast.reward(
            'Посещение отмечено!',
            `+${rewards.coins} монет · +${rewards.intelligence_points} интеллекта · +${rewards.satisfaction} настроения${livesRewardText(rewards.lives_added)}`
          );
        } else {
          toast.success('Посещение отмечено', 'Награды будут начислены чуть позже.');
        }
        if (result.character?.level_up) {
          toast.reward('Новый уровень!', `Интеллект персонажа вырос до ${result.character.intelligence_level}`);
        }
        (result.unlocked_sets ?? []).forEach((set) => toast.reward('Открыт новый сет', set.name));
        if (result.character?.satisfaction != null) {
          dispatch({ type: 'MERGE_CHARACTER', patch: { satisfaction: result.character.satisfaction } });
        }
        await Promise.allSettled([refreshUserAndCharacter(), loadSchedule(), loadStreak()]);
      } catch (error) {
        haptic('error');
        setCheckInError(error?.message ?? 'Не удалось отметиться. Проверьте соединение и попробуйте ещё раз.');
      } finally {
        setSubmitting(false);
      }
    },
    [user?.id, dispatch, refreshUserAndCharacter, loadSchedule, loadStreak]
  );

  // Отметка по QR-диплинку: мини-приложение открыто ссылкой ?startapp=att-<id>-<код>
  useEffect(() => {
    if (!pendingCheckIn || !user?.id) return;
    dispatch({ type: 'SET_PENDING_CHECKIN', value: null });
    submitCheckIn(pendingCheckIn.lessonId, pendingCheckIn.code, 'qr');
  }, [pendingCheckIn, user?.id, dispatch, submitCheckIn]);

  const handleJoin = useCallback(
    async (code) => {
      try {
        const result = await joinByCode(user.id, code);
        toast.success(result.kind === 'curator' ? 'Вы куратор группы' : 'Вы в группе!', result.group.name);
        await Promise.allSettled([refreshUserAndCharacter(), loadSchedule(), loadStreak()]);
      } catch (error) {
        toast.error('Не удалось вступить', error?.message);
      }
    },
    [user?.id, refreshUserAndCharacter, loadSchedule, loadStreak]
  );

  const handleShare = useCallback(async () => {
    const config = await loadAppConfig();
    const streakText = streak?.current ? `Серия посещений — ${streak.current}.` : 'Отметился на паре.';
    const result = await shareContent({
      text: `${streakText} Мой персонаж в «Матриксе» растёт, когда я хожу на пары. Присоединяйся!`,
      link: config?.bot_link || window.location.origin
    });
    if (result === 'copied') toast.success('Ссылка скопирована');
  }, [streak?.current]);

  const handleHelp = useCallback(async () => {
    setHelpState('sending');
    try {
      const result = await requestSupport(user.id);
      setHelpState('sent');
      toast.success(
        'Куратор получил сообщение',
        result.curators_notified ? 'С тобой свяжутся. Ты не один.' : 'Куратор пока не назначен — обратись в деканат или к психологу вуза.'
      );
    } catch (error) {
      setHelpState('idle');
      toast.error('Не отправлено', error?.message);
    }
  }, [user?.id]);

  const satisfaction = character?.satisfaction ?? null;
  // Мягкий сигнал поддержки: персонаж грустит или накопились пропуски
  const showHelp =
    helpState !== 'hidden' &&
    ((satisfaction != null && satisfaction < 25) || (streak?.pending_misses?.length ?? 0) >= 2 || (streak?.current === 0 && streak?.best >= 3));
  const mood = character?.mood ?? (satisfaction != null ? moodFromSatisfaction(satisfaction) : null);
  const level = character?.intelligence_level ?? 1;
  const pointsToNext = level * 100;

  return (
    <div className="today">
      <div className="hero">
        <CharacterViewer
          ref={viewerRef}
          satisfaction={satisfaction}
          growthStage={character?.growth_stage ?? 'teen'}
          characterKey={character?.active_character_set?.asset_key}
          environmentKey={character?.active_environment_set?.asset_key}
          environmentTheme={character?.active_environment_set?.theme_id}
          isActive={isActive}
        />
        <div className="hero__top">
          <span className="hero-chip" title="Настроение персонажа">
            <StatIcon kind="satisfaction" size={16} />
            {(mood && MOOD_LABELS[mood]) || '—'} · {satisfaction ?? '—'}%
          </span>
          <span className="hero-chip" title="Уровень интеллекта">
            <StatIcon kind="intelligence" size={16} />
            ур. {level}
          </span>
          <button type="button" className="hero-chip hero-chip--button" onClick={() => setWardrobeOpen(true)}>
            <Shirt size={16} aria-hidden="true" />
            Гардероб
          </button>
        </div>
        {burst ? (
          <div key={burst.id} className="today-burst" aria-hidden="true">
            <RewardChips
              rewards={{ coins: burst.coins, intelligence: burst.intelligence_points, satisfaction: burst.satisfaction }}
              size={16}
            />
          </div>
        ) : null}
        <div className="hero__bars">
          <div className="hero-bar">
            <span className="hero-bar__label">Настроение</span>
            <div className="hero-bar__track">
              <div className="hero-bar__fill hero-bar__fill--mood" style={{ width: `${Math.max(0, Math.min(100, satisfaction ?? 0))}%` }} />
            </div>
          </div>
          <div className="hero-bar">
            <span className="hero-bar__label">До ур. {level + 1}</span>
            <div className="hero-bar__track">
              <div
                className="hero-bar__fill hero-bar__fill--mind"
                style={{ width: `${Math.max(0, Math.min(100, ((character?.intelligence_points ?? 0) / pointsToNext) * 100))}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      <CheckInCard
        schedule={schedule}
        scheduleState={scheduleState}
        onRetrySchedule={loadSchedule}
        onSubmit={submitCheckIn}
        submitting={submitting}
        lastResult={lastResult}
        error={checkInError}
        onClearError={() => setCheckInError(null)}
        onJoin={handleJoin}
        onShare={handleShare}
      />

      {showHelp ? (
        <Card className="help-card">
          <div className="help-card__title inline-icon">
            <LifeBuoy size={18} aria-hidden="true" /> Кажется, сейчас непросто
          </div>
          <p className="help-card__text">
            Персонаж грустит, а пропуски копятся. Если что-то мешает учёбе — куратор группы поможет разобраться. Просить поддержку
            нормально.
          </p>
          <div className="help-card__actions">
            <Button size="sm" loading={helpState === 'sending'} disabled={helpState === 'sent'} onClick={handleHelp}>
              {helpState === 'sent' ? 'Сообщение отправлено' : 'Написать куратору'}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setHelpState('hidden')}>
              Всё хорошо
            </Button>
          </div>
        </Card>
      ) : null}

      <GameCard isActive={isActive} />

      <StreakCard userId={user?.id} streak={streak} state={streakState} onRetry={loadStreak} onChanged={loadStreak} />

      <div className="today__secondary">
        <Button
          variant="ghost"
          size="sm"
          icon={<CalendarDays size={16} aria-hidden="true" />}
          onClick={() => dispatch({ type: 'SET_ACTIVE_SECTION', section: 'events' })}
        >
          Все пары и события
        </Button>
      </div>

      <WardrobeModal
        isOpen={wardrobeOpen}
        onClose={() => setWardrobeOpen(false)}
        userId={user?.id}
        coins={user?.coins}
        onChanged={() => refreshUserAndCharacter()}
      />
    </div>
  );
}
