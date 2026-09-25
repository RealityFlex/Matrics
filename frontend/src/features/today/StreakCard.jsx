import React, { useState } from 'react';
import { Button, Card, StateView } from '../../components/ui/index.jsx';
import { freezeMiss } from '../../services/events.js';
import { toast } from '../../components/ui/toast.jsx';
import { StatIcon } from '../../components/ui/icons.jsx';

function formatDeadline(iso) {
  try {
    return new Date(iso).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}

/**
 * Серия посещений и «день без штрафа» — мягкая механика поддержки:
 * пропуск можно «заморозить» ограниченное число раз, без потери настроения персонажа.
 */
export function StreakCard({ userId, streak, state, onRetry, onChanged }) {
  const [freezingId, setFreezingId] = useState(null);

  if (state === 'loading') {
    return (
      <Card className="streak-card">
        <StateView state="loading" message="Считаем серию…" compact />
      </Card>
    );
  }
  if (state === 'error' || !streak) {
    return (
      <Card className="streak-card">
        <StateView state="error" title="Серия недоступна" onRetry={onRetry} compact />
      </Card>
    );
  }

  const handleFreeze = async (missId) => {
    setFreezingId(missId);
    try {
      await freezeMiss(userId, missId);
      toast.success('День без штрафа', 'Пропуск не повлияет на персонажа и серию.');
      onChanged?.();
    } catch (error) {
      toast.error('Не получилось', error?.message ?? 'Попробуйте ещё раз');
    } finally {
      setFreezingId(null);
    }
  };

  const pending = streak.pending_misses ?? [];

  return (
    <Card className="streak-card">
      <div className="streak-card__row">
        <div className="streak-card__flame" aria-hidden="true">
          <StatIcon kind="streak" size={30} />
        </div>
        <div className="streak-card__main">
          <div className="streak-card__value tabular">{streak.current}</div>
          <div className="streak-card__label">пар подряд · рекорд {streak.best}</div>
        </div>
        <div className="streak-card__freezes" title="«Дни без штрафа» на 30 дней">
          <StatIcon kind="freeze" size={16} />
          <span className="tabular">
            {streak.freezes_available}/{streak.freezes_limit}
          </span>
        </div>
      </div>
      {pending.length ? (
        <div className="streak-card__pending">
          {pending.map((miss) => (
            <div key={miss.miss_id} className="miss-row">
              <div>
                <div className="miss-row__title">Пропуск: {miss.lesson_name}</div>
                <div className="miss-row__meta">Решить до {formatDeadline(miss.deadline)}</div>
              </div>
              <Button
                size="sm"
                variant="secondary"
                loading={freezingId === miss.miss_id}
                disabled={!streak.freezes_available}
                onClick={() => handleFreeze(miss.miss_id)}
              >
                {streak.freezes_available ? 'Без штрафа' : 'Лимит исчерпан'}
              </Button>
            </div>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
