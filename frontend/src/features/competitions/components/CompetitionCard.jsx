import React, { useState, useEffect, useCallback } from 'react';
import { useAppState } from '../../../state/AppProvider.jsx';
import { getCompetitionLeaderboard, joinCompetition, declineCompetition, getUserCompetitionParticipation, getUserCompetitionProgress } from '../../../services/competitions.js';
import { getUser } from '../../../services/users.js';
import { useRefreshUserAndCharacter } from '../../../hooks/useRefreshUserAndCharacter.js';
import { NotificationModal } from '../../../components/common/NotificationModal.jsx';
import { Badge, Button, ProgressBar, Spinner } from '../../../components/ui/index.jsx';
import { StatValue } from '../../../components/ui/icons.jsx';
import { CalendarClock, CheckCircle2, Flag, Medal, Target, Trophy } from 'lucide-react';
import { metricLabel } from '../metrics.js';

function formatDateTime(value) {
  if (!value) {
    return '—';
  }
  return new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

const PLACES = [
  { key: 'first_place_coins', label: '1 место', tone: 'gold' },
  { key: 'second_place_coins', label: '2 место', tone: 'silver' },
  { key: 'third_place_coins', label: '3 место', tone: 'bronze' }
];

export function CompetitionCard({ competition, onUpdate }) {
  const { user } = useAppState();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();
  const [top3, setTop3] = useState([]);
  const [isLoadingResults, setIsLoadingResults] = useState(false);
  const [isParticipant, setIsParticipant] = useState(false);
  const [isLoadingParticipation, setIsLoadingParticipation] = useState(false);
  const [isActionLoading, setIsActionLoading] = useState(false);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [progress, setProgress] = useState(null);
  const [isLoadingProgress, setIsLoadingProgress] = useState(false);

  const loadTop3 = useCallback(async () => {
    setIsLoadingResults(true);
    try {
      const leaderboard = await getCompetitionLeaderboard(competition.id);
      const top3Participants = leaderboard.slice(0, 3);
      
      // Загрузить информацию о пользователях
      const top3WithUsers = await Promise.all(
        top3Participants.map(async (participant) => {
          try {
            const user = await getUser(participant.user_id);
            return {
              ...participant,
              username: user.username || `Пользователь #${participant.user_id}`
            };
          } catch (error) {
            console.error(`Ошибка загрузки пользователя ${participant.user_id}:`, error);
            return {
              ...participant,
              username: `Пользователь #${participant.user_id}`
            };
          }
        })
      );
      
      setTop3(top3WithUsers);
    } catch (error) {
      console.error('Ошибка загрузки результатов:', error);
    } finally {
      setIsLoadingResults(false);
    }
  }, [competition.id]);

  const checkParticipation = useCallback(async () => {
    if (!user?.id) return;
    setIsLoadingParticipation(true);
    try {
      const participation = await getUserCompetitionParticipation(competition.id, user.id);
      setIsParticipant(!!participation);
    } catch (error) {
      console.error('Ошибка проверки участия:', error);
      setIsParticipant(false);
    } finally {
      setIsLoadingParticipation(false);
    }
  }, [user?.id, competition.id]);

  const loadProgress = useCallback(async () => {
    if (!user?.id || !competition.metric_type) return;
    setIsLoadingProgress(true);
    try {
      const progressData = await getUserCompetitionProgress(competition.id, user.id);
      setProgress(progressData);
    } catch (error) {
      console.error('Ошибка загрузки прогресса:', error);
      setProgress(null);
    } finally {
      setIsLoadingProgress(false);
    }
  }, [user?.id, competition.id, competition.metric_type]);

  useEffect(() => {
    if (competition.is_finished) {
      loadTop3();
    }
  }, [competition.is_finished, loadTop3]);

  useEffect(() => {
    if (user?.id && !competition.is_finished) {
      // Проверяем участие только один раз при загрузке карточки
      checkParticipation();
    }
  }, [user?.id, competition.is_finished, checkParticipation]);

  useEffect(() => {
    if (user?.id && !competition.is_finished && competition.metric_type && isParticipant) {
      loadProgress();
      // Обновлять прогресс каждые 30 секунд
      const interval = setInterval(() => {
        loadProgress();
      }, 30000);
      return () => clearInterval(interval);
    }
  }, [user?.id, competition.is_finished, competition.metric_type, isParticipant, loadProgress]);

  const handleJoin = async () => {
    if (!user?.id || isActionLoading) return;
    setIsActionLoading(true);
    try {
      await joinCompetition(competition.id, user.id);
      setIsParticipant(true);
      if (refreshUserAndCharacter) {
        await refreshUserAndCharacter();
      }
      if (competition.metric_type) {
        await loadProgress();
      }
      if (onUpdate) onUpdate();
      setNotification({
        isOpen: true,
        message: 'Вы успешно присоединились к соревнованию!',
        type: 'success',
        title: 'Успешно'
      });
    } catch (error) {
      setNotification({
        isOpen: true,
        message: error.message ?? 'Не удалось присоединиться к соревнованию',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleDecline = async () => {
    if (!user?.id || isActionLoading) return;
    setIsActionLoading(true);
    try {
      await declineCompetition(competition.id, user.id);
      setIsParticipant(false);
      if (onUpdate) onUpdate();
      setNotification({
        isOpen: true,
        message: 'Вы отказались от участия в соревновании',
        type: 'info',
        title: 'Информация'
      });
    } catch (error) {
      setNotification({
        isOpen: true,
        message: error.message ?? 'Не удалось отказаться от соревнования',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsActionLoading(false);
    }
  };

  const metric = competition.metric_type ? metricLabel(competition.metric_type) : null;
  const statusLabel = competition.is_finished ? 'Завершено' : competition.is_active ? 'Идёт' : 'Не активно';
  const statusTone = competition.is_finished ? 'neutral' : competition.is_active ? 'success' : 'warning';
  const prizes = PLACES.filter((place) => competition[place.key]);

  return (
    <div className="card comp-card">
      <div className="card-header">
        <div className="card-title">{competition.name}</div>
        <Badge tone={statusTone}>{statusLabel}</Badge>
      </div>
      {competition.description ? <div className="card-description">{competition.description}</div> : null}
      {metric ? (
        <div className="comp-card__condition">
          <span className="inline-icon">
            <Target size={16} aria-hidden="true" />
            <span>
              Условие: <strong>{metric}</strong>
            </span>
          </span>
          {competition.target_value ? <span className="comp-card__target">Цель: {competition.target_value}</span> : null}
        </div>
      ) : null}
      <div className="comp-card__dates">
        <span className="inline-icon">
          <CalendarClock size={14} aria-hidden="true" /> Старт: {formatDateTime(competition.start_time)}
        </span>
        <span className="inline-icon">
          <Flag size={14} aria-hidden="true" /> Финиш: {formatDateTime(competition.end_time)}
        </span>
      </div>
      {prizes.length ? (
        <div className="comp-card__prizes" aria-label="Призы">
          {prizes.map((place) => (
            <span key={place.key} className="comp-prize">
              <Medal size={14} className={`comp-medal comp-medal--${place.tone}`} aria-hidden="true" />
              <span className="comp-prize__place">{place.label}</span>
              <StatValue kind="coins" value={competition[place.key]} size={14} />
            </span>
          ))}
        </div>
      ) : null}
      {competition.is_finished && (
        <div className="comp-card__results">
          <div className="comp-card__results-title inline-icon">
            <Trophy size={18} aria-hidden="true" /> Результаты
          </div>
          {isLoadingResults ? (
            <Spinner size="sm" label="Загружаем результаты…" />
          ) : top3.length === 0 ? (
            <div className="comp-card__muted">Результатов пока нет</div>
          ) : (
            <ol className="comp-leaders">
              {top3.map((participant, index) => {
                const metricValue =
                  participant.metric_value !== null && participant.metric_value !== undefined
                    ? participant.metric_value
                    : participant.score || 0;
                return (
                  <li key={participant.id} className="comp-leader">
                    <span className="comp-leader__rank">
                      <Medal size={18} className={`comp-medal comp-medal--${PLACES[index]?.tone}`} aria-hidden="true" />
                      <span className="visually-hidden">{index + 1} место</span>
                    </span>
                    <span className="comp-leader__name">{participant.username}</span>
                    <span className="comp-leader__value tabular">
                      {metricValue}
                      <span className="comp-leader__metric"> · {metric ?? 'очки'}</span>
                    </span>
                  </li>
                );
              })}
            </ol>
          )}
        </div>
      )}
      {!competition.is_finished && competition.is_active && user?.id && (
        <div className="comp-card__actions">
          {isLoadingParticipation ? (
            <Spinner size="sm" label="Проверяем участие…" />
          ) : isParticipant ? (
            <>
              <div className="checkin-card__done" role="status">
                <CheckCircle2 size={18} aria-hidden="true" />
                <span>Вы участвуете в этом соревновании</span>
              </div>
              {progress && metric ? (
                <div className="comp-card__progress">
                  <div className="comp-card__muted">
                    Ваш прогресс: <strong>{progress.current_value}</strong> · {metric}
                  </div>
                  {competition.target_value && progress.remaining !== null ? (
                    progress.remaining === 0 ? (
                      <div className="comp-card__goal-done inline-icon">
                        <Trophy size={16} aria-hidden="true" /> Цель достигнута!
                      </div>
                    ) : (
                      <ProgressBar
                        value={Math.min(progress.current_value, competition.target_value)}
                        max={competition.target_value}
                        label={`Осталось: ${progress.remaining}`}
                        showValue
                        tone="primary"
                      />
                    )
                  ) : null}
                </div>
              ) : null}
            </>
          ) : (
            <div className="comp-card__buttons">
              <Button block loading={isActionLoading} onClick={handleJoin}>
                Присоединиться
              </Button>
              <Button block variant="ghost" size="sm" disabled={isActionLoading} onClick={handleDecline}>
                Отказаться
              </Button>
            </div>
          )}
        </div>
      )}
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
    </div>
  );
}
