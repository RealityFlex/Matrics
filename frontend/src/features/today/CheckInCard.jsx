import React, { useEffect, useRef, useState } from 'react';
import { Camera, CheckCircle2, Users } from 'lucide-react';
import { Badge, Button, Card, ProgressBar, StateView } from '../../components/ui/index.jsx';
import { RewardChips, StatValue } from '../../components/ui/icons.jsx';
import { canScanQr, scanQr } from '../../utils/maxBridge.js';
import { parseCheckinPayload } from '../../services/events.js';

function formatTime(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

function formatDay(iso) {
  try {
    const date = new Date(iso);
    const today = new Date();
    const tomorrow = new Date();
    tomorrow.setDate(today.getDate() + 1);
    if (date.toDateString() === today.toDateString()) return 'сегодня';
    if (date.toDateString() === tomorrow.toDateString()) return 'завтра';
    return date.toLocaleDateString('ru-RU', { weekday: 'short', day: 'numeric', month: 'short' });
  } catch {
    return '';
  }
}

/** Командная цель: когда отметится N% группы — бонус всем отметившимся */
function GroupGoal({ goal }) {
  if (!goal || !goal.expected) return null;
  return (
    <div className={`group-goal ${goal.achieved ? 'group-goal--done' : ''}`}>
      <div className="group-goal__head">
        <span className="inline-icon">
          <Users size={16} aria-hidden="true" /> {goal.group_name}: {goal.attended} из {goal.expected}
        </span>
        <span className="tabular">{goal.percent}% / {goal.target_percent}%</span>
      </div>
      <ProgressBar value={goal.percent} max={100} tone={goal.achieved ? 'success' : 'reward'} />
      <div className="group-goal__hint">
        {goal.achieved ? (
          <>
            Командная цель выполнена — бонус{' '}
            <StatValue kind="coins" value={goal.bonus?.coins ?? 0} signed size={14} />{' '}
            <StatValue kind="satisfaction" value={goal.bonus?.satisfaction ?? 0} signed size={14} /> каждому отметившемуся
          </>
        ) : (
          `Ещё ${goal.needed} ${goal.needed === 1 ? 'отметка' : 'отметок'} до командного бонуса — позови одногруппников!`
        )}
      </div>
    </div>
  );
}

function JoinByCode({ onJoin }) {
  const [code, setCode] = useState('');
  const [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    if (!code.trim()) return;
    setBusy(true);
    try {
      await onJoin(code.trim());
      setCode('');
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="code-form" onSubmit={submit}>
      <label className="code-form__label" htmlFor="join-code">Код группы из приглашения</label>
      <div className="code-form__row">
        <input id="join-code" className="code-input code-input--text" value={code} placeholder="ABCD1234"
               onChange={(event) => setCode(event.target.value.toUpperCase())} maxLength={20} autoComplete="off" />
        <Button type="submit" size="lg" loading={busy} disabled={!code.trim()}>Вступить</Button>
      </div>
    </form>
  );
}

function LessonRewards({ lesson }) {
  return (
    <div aria-label="Награда за посещение">
      <RewardChips
        rewards={{
          coins: lesson.reward_coins,
          intelligence: lesson.reward_intelligence_points,
          satisfaction: lesson.reward_satisfaction
        }}
      />
    </div>
  );
}

/**
 * Карточка основного действия: отметиться на текущей паре.
 * Состояния: загрузка расписания → нет групп / нет пары / пара идёт → отправка → успех/ошибка.
 */
export function CheckInCard({ schedule, scheduleState, onRetrySchedule, onSubmit, submitting, lastResult, error, onClearError, onJoin, onShare }) {
  const [code, setCode] = useState('');
  const inputRef = useRef(null);
  const current = schedule?.current ?? null;
  const next = schedule?.next ?? null;
  const qrAvailable = canScanQr();

  useEffect(() => {
    if (lastResult?.status === 'checked_in') {
      setCode('');
    }
  }, [lastResult]);

  const handleScan = async () => {
    onClearError?.();
    try {
      const value = await scanQr();
      if (!value) return;
      const payload = parseCheckinPayload(value);
      if (!payload) {
        onSubmit(null, null, 'qr', 'Это не QR-код занятия. Попросите преподавателя показать код отметки.');
        return;
      }
      onSubmit(payload.lessonId, payload.code, 'qr');
    } catch (scanError) {
      onSubmit(null, null, 'qr', scanError?.message ?? 'Не удалось открыть сканер');
    }
  };

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!current || code.length !== 4) return;
    onSubmit(current.id, code, 'code');
  };

  if (scheduleState === 'loading') {
    return (
      <Card className="checkin-card">
        <StateView state="loading" message="Загружаем расписание…" compact />
      </Card>
    );
  }

  if (scheduleState === 'error') {
    return (
      <Card className="checkin-card">
        <StateView state="error" title="Не удалось загрузить расписание" message="Проверьте соединение и попробуйте ещё раз." onRetry={onRetrySchedule} compact />
      </Card>
    );
  }

  if (!schedule?.has_groups) {
    return (
      <Card className="checkin-card">
        <StateView
          state="empty"
          title="Вы пока не в учебной группе"
          message="Откройте ссылку-приглашение от куратора или введите код группы — тогда здесь появятся пары, и за каждую отметку персонаж будет расти."
          compact
        />
        {onJoin ? <JoinByCode onJoin={onJoin} /> : null}
      </Card>
    );
  }

  const alreadyAttended = current?.attended || (lastResult && lastResult.lesson?.id === current?.id);

  return (
    <Card className={`checkin-card ${current ? 'checkin-card--live' : ''}`}>
      <div className="checkin-card__eyebrow">
        {current ? (
          <Badge tone="success">Идёт сейчас</Badge>
        ) : next ? (
          <Badge tone="neutral">Следующая пара · {formatDay(next.start_time)}</Badge>
        ) : (
          <Badge tone="neutral">Сегодня пар больше нет</Badge>
        )}
        {(current ?? next)?.is_simulated ? <Badge tone="warning" title="Расписание загружено из тестового файла">Тестовые данные</Badge> : null}
      </div>

      {current || next ? (
        <>
          <h2 className="checkin-card__title">{(current ?? next).name}</h2>
          <div className="checkin-card__meta">
            {formatTime((current ?? next).start_time)}–{formatTime((current ?? next).end_time)}
            {(current ?? next).location ? ` · ${(current ?? next).location}` : ''}
          </div>
          <LessonRewards lesson={current ?? next} />
        </>
      ) : (
        <p className="checkin-card__hint">Отдыхайте! Отметиться можно будет, когда начнётся следующая пара.</p>
      )}

      {current && alreadyAttended ? (
        <div className="checkin-card__done" role="status">
          <CheckCircle2 size={18} aria-hidden="true" />
          <span>Вы отмечены на этой паре. Награда уже у персонажа!</span>
          {onShare ? (
            <Button size="sm" variant="ghost" onClick={onShare}>
              Поделиться
            </Button>
          ) : null}
        </div>
      ) : null}

      {current ? <GroupGoal goal={(lastResult?.lesson?.id === current.id && lastResult?.group_goal) || current.group_goal} /> : null}

      {current && !alreadyAttended ? (
        <div className="checkin-card__actions">
          {qrAvailable ? (
            <Button size="lg" block onClick={handleScan} loading={submitting} icon={<Camera size={18} aria-hidden="true" />}>
              Сканировать QR
            </Button>
          ) : null}
          <form className="code-form" onSubmit={handleSubmit} noValidate>
            <label className="code-form__label" htmlFor="checkin-code">
              {qrAvailable ? 'Или введите код с экрана' : 'Код с экрана преподавателя'}
            </label>
            <div className="code-form__row">
              <input
                id="checkin-code"
                ref={inputRef}
                className={`code-input ${error ? 'is-invalid' : ''}`}
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]*"
                maxLength={4}
                placeholder="0000"
                value={code}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? 'checkin-error' : undefined}
                onChange={(event) => {
                  onClearError?.();
                  setCode(event.target.value.replace(/\D/g, '').slice(0, 4));
                }}
              />
              <Button
                type="submit"
                size="lg"
                variant={qrAvailable ? 'secondary' : 'primary'}
                loading={submitting}
                disabled={code.length !== 4}
              >
                Отметиться
              </Button>
            </div>
          </form>
        </div>
      ) : null}

      {error ? (
        <div id="checkin-error" className="inline-error" role="alert">
          {error}
        </div>
      ) : null}
    </Card>
  );
}
