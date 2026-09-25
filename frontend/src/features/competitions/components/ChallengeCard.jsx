import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Check, Hourglass, X } from 'lucide-react';
import { Badge, Button } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';
import { challengeStatus, metricLabel } from '../metrics.js';

function formatDate(value) {
  if (!value) {
    return '—';
  }
  return new Date(value).toLocaleString('ru-RU', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function ChallengeCard({ challenge, currentUserId, onAccept, onDecline, isProcessing }) {
  const [showDetails, setShowDetails] = useState(false);
  const isChallenger = challenge.challenger_id === currentUserId;
  const opponentId = isChallenger ? challenge.opponent_id : challenge.challenger_id;
  const userProgress = isChallenger ? challenge.challenger_progress : challenge.opponent_progress;
  const opponentProgress = isChallenger ? challenge.opponent_progress : challenge.challenger_progress;
  const isPending = challenge.status?.toLowerCase() === 'pending';
  const canRespond = isPending && !isChallenger;

  const handleAccept = () => {
    if (onAccept) {
      onAccept(challenge.id);
    }
  };

  const handleDecline = () => {
    if (onDecline) {
      onDecline(challenge.id);
    }
  };

  const status = challengeStatus(challenge.status);

  return (
    <div className="card comp-card">
      <div className="card-header">
        <div className="card-title">
          {isChallenger ? 'Вы против ' : 'Вас вызвал '}#{opponentId}
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>

      <div className="challenge-card__score">
        <span className="challenge-card__me">
          Вы: <strong className="tabular">{userProgress}</strong>
        </span>
        <span className="challenge-card__them">
          Соперник: <span className="tabular">{opponentProgress}</span>
        </span>
        <RewardChips rewards={{ coins: challenge.reward_coins, intelligence: challenge.reward_intelligence_points }} signed={false} />
      </div>

      {showDetails ? (
        <dl className="challenge-card__details">
          <div>
            <dt>Показатель</dt>
            <dd>{metricLabel(challenge.metric_type)}</dd>
          </div>
          <div>
            <dt>Цель</dt>
            <dd className="tabular">{challenge.target_value}</dd>
          </div>
          <div>
            <dt>До цели</dt>
            <dd className="tabular">{Math.max(0, challenge.target_value - userProgress)}</dd>
          </div>
          <div>
            <dt>Дедлайн</dt>
            <dd>{formatDate(challenge.deadline)}</dd>
          </div>
          {challenge.completed_at ? (
            <div>
              <dt>Завершено</dt>
              <dd>{formatDate(challenge.completed_at)}</dd>
            </div>
          ) : null}
          {challenge.winner_id ? (
            <div>
              <dt>Победитель</dt>
              <dd>{challenge.winner_id === currentUserId ? 'Вы' : `#${challenge.winner_id}`}</dd>
            </div>
          ) : null}
        </dl>
      ) : null}

      <Button
        variant="ghost"
        size="sm"
        className="challenge-card__toggle"
        aria-expanded={showDetails}
        icon={showDetails ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
        onClick={() => setShowDetails(!showDetails)}
      >
        {showDetails ? 'Скрыть' : 'Подробнее'}
      </Button>

      {canRespond ? (
        <div className="comp-card__buttons comp-card__buttons--row">
          <Button size="sm" loading={isProcessing} icon={<Check size={16} aria-hidden="true" />} onClick={handleAccept}>
            Принять
          </Button>
          <Button size="sm" variant="secondary" disabled={isProcessing} icon={<X size={16} aria-hidden="true" />} onClick={handleDecline}>
            Отклонить
          </Button>
        </div>
      ) : null}
      {isPending && isChallenger ? (
        <div className="comp-card__muted inline-icon">
          <Hourglass size={14} aria-hidden="true" /> Ждём ответа соперника
        </div>
      ) : null}
    </div>
  );
}
