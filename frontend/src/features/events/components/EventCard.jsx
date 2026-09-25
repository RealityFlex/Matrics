import React, { useEffect, useState } from 'react';
import {
  checkInLesson,
  getUserEventAttendance,
  getUserLessonAttendance,
  registerForEvent,
  verifyEventCode
} from '../../../services/events.js';
import { useAppState } from '../../../state/AppProvider.jsx';
import { useRefreshUserAndCharacter } from '../../../hooks/useRefreshUserAndCharacter.js';
import { Badge, Button } from '../../../components/ui/index.jsx';
import { toast } from '../../../components/ui/toast.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';
import { CheckCircle2, Clock, KeyRound, MapPin, UserCheck } from 'lucide-react';

function formatDate(dateString) {
  if (!dateString) {
    return '—';
  }
  return new Date(dateString).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function EventCard({ event, onUpdate }) {
  const { user } = useAppState();
  const refreshUserAndCharacter = useRefreshUserAndCharacter();
  const [isLoading, setIsLoading] = useState(false);
  const [attendance, setAttendance] = useState(null);
  const [lessonAttendance, setLessonAttendance] = useState(null);
  const [codeInput, setCodeInput] = useState('');
  const [showCodeInput, setShowCodeInput] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');

  const isLesson = event.type === 'lesson';

  useEffect(() => {
    if (!user?.id || !event?.id) return;
    if (isLesson) {
      getUserLessonAttendance(event.id, user.id).then(setLessonAttendance).catch(() => setLessonAttendance(null));
    } else {
      getUserEventAttendance(event.id, user.id).then(setAttendance).catch(() => setAttendance(null));
    }
  }, [user?.id, event?.id, isLesson]);

  const handleRegister = async () => {
    if (!user?.id) return;
    setIsLoading(true);
    setErrorMessage('');
    try {
      await registerForEvent(event.id, user.id);
      setAttendance(await getUserEventAttendance(event.id, user.id));
      onUpdate?.();
      toast.success('Вы зарегистрированы', event.name);
    } catch (error) {
      if (error.message?.includes('уже зарегистрирован')) {
        setAttendance(await getUserEventAttendance(event.id, user.id));
        toast.info('Вы уже зарегистрированы', event.name);
      } else {
        setErrorMessage(error.message ?? 'Не удалось зарегистрироваться на событие');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleVerifyCode = async (submitEvent) => {
    submitEvent?.preventDefault();
    if (!user?.id || !/^\d{4}$/.test(codeInput)) {
      setErrorMessage('Код должен состоять из 4 цифр');
      return;
    }
    setIsLoading(true);
    setErrorMessage('');
    try {
      if (isLesson) {
        const result = await checkInLesson(event.id, user.id, codeInput, 'code');
        setLessonAttendance(await getUserLessonAttendance(event.id, user.id));
        if (result.status === 'already') {
          toast.info('Вы уже отмечены', event.name);
        } else {
          const rewards = result.rewards ?? {};
          toast.reward('Посещение отмечено!', `+${rewards.coins} монет · +${rewards.intelligence_points} интеллекта · +${rewards.satisfaction} настроения`);
        }
      } else {
        await verifyEventCode(event.id, user.id, codeInput);
        setAttendance(await getUserEventAttendance(event.id, user.id));
        toast.reward('Посещение отмечено!', 'Награды начислены');
      }
      setCodeInput('');
      setShowCodeInput(false);
      await refreshUserAndCharacter?.();
      onUpdate?.();
    } catch (error) {
      setErrorMessage(error.message ?? 'Неверный код');
    } finally {
      setIsLoading(false);
    }
  };

  const attended = isLesson ? Boolean(lessonAttendance) : Boolean(attendance?.attended);
  const canEnterCode = isLesson ? !lessonAttendance : attendance && !attendance.attended;

  return (
    <div className="card event-card">
      <div className="card-header">
        <div className="card-title">{event.name}</div>
        <div className="event-card__badges">
          {event.is_simulated ? <Badge tone="warning">Тестовые данные</Badge> : null}
          {isLesson ? <Badge tone="info">Занятие</Badge> : <Badge>{event.is_public ? 'Открыто' : 'Приватно'}</Badge>}
        </div>
      </div>
      {event.description ? <div className="card-description">{event.description}</div> : null}
      {isLesson && event.groups?.length ? (
        <div className="event-card__meta">Группы: {event.groups.map((g) => g.name || `Группа #${g.id}`).join(', ')}</div>
      ) : null}
      <div className="event-card__meta event-card__meta-row">
        <span className="inline-icon">
          <MapPin size={14} aria-hidden="true" /> {event.location ?? 'Место не указано'}
        </span>
        <span className="inline-icon">
          <Clock size={14} aria-hidden="true" /> {formatDate(event.start_time)}
          {event.end_time ? ` – ${formatDate(event.end_time)}` : ''}
        </span>
      </div>
      <RewardChips
        rewards={{
          coins: event.reward_coins,
          intelligence: event.reward_intelligence_points,
          satisfaction: isLesson ? event.reward_satisfaction : 0
        }}
      />

      {attended ? (
        <div className="checkin-card__done" role="status">
          <CheckCircle2 size={18} aria-hidden="true" />
          <span>{isLesson ? 'Посещение отмечено' : 'Вы посетили это событие'}</span>
        </div>
      ) : null}
      {!isLesson && attendance && !attendance.attended ? (
        <div className="event-card__note inline-icon">
          <UserCheck size={16} aria-hidden="true" />
          <span>Вы зарегистрированы — на месте введите код с экрана организатора</span>
        </div>
      ) : null}

      {!isLesson && !attendance ? (
        <Button block loading={isLoading} onClick={handleRegister}>
          Зарегистрироваться
        </Button>
      ) : null}

      {canEnterCode && !showCodeInput ? (
        <Button block variant="secondary" icon={<KeyRound size={16} aria-hidden="true" />} onClick={() => setShowCodeInput(true)}>
          Ввести код
        </Button>
      ) : null}

      {canEnterCode && showCodeInput ? (
        <form className="code-form__row" onSubmit={handleVerifyCode}>
          <input
            className={`code-input ${errorMessage ? 'is-invalid' : ''}`}
            inputMode="numeric"
            pattern="[0-9]*"
            placeholder="0000"
            maxLength={4}
            value={codeInput}
            autoFocus
            disabled={isLoading}
            aria-label="Код с экрана"
            onChange={(e) => {
              setErrorMessage('');
              setCodeInput(e.target.value.replace(/\D/g, '').slice(0, 4));
            }}
          />
          <Button type="submit" size="lg" loading={isLoading} disabled={codeInput.length !== 4}>
            Отметиться
          </Button>
        </form>
      ) : null}

      {errorMessage ? (
        <div className="inline-error" role="alert">
          {errorMessage}
        </div>
      ) : null}
    </div>
  );
}
