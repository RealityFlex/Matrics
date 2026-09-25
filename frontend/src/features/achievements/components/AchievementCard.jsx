import React from 'react';
import { Award, Brain, CalendarCheck, CalendarDays, Coins, Flame, ListChecks, Lock, Repeat } from 'lucide-react';
import { Badge, ProgressBar } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';

// Тип требования → иконка и понятная подпись прогресса (эмодзи из БД не показываем)
const REQUIREMENTS = {
  lessons_attended: { Icon: CalendarCheck, label: 'Посещено занятий' },
  attendance_streak: { Icon: Flame, label: 'Лучшая серия посещений' },
  tasks_completed: { Icon: ListChecks, label: 'Выполнено задач' },
  habits_logged: { Icon: Repeat, label: 'Отмечено привычек' },
  events_attended: { Icon: CalendarDays, label: 'Посещено событий' },
  coins_earned: { Icon: Coins, label: 'Заработано монет' },
  coins: { Icon: Coins, label: 'Монет на счету' },
  intelligence_points_earned: { Icon: Brain, label: 'Заработано очков интеллекта' },
  intelligence_points: { Icon: Brain, label: 'Очков интеллекта' }
};

export function requirementInfo(type) {
  return REQUIREMENTS[type] ?? { Icon: Award, label: 'Прогресс' };
}

export function AchievementCard({ achievement, earnedAt, isCompleted, progress = 0 }) {
  const earned = isCompleted || Boolean(earnedAt);
  const target = achievement.requirement_value ?? 0;
  const { Icon, label } = requirementInfo(achievement.requirement_type);

  return (
    <div className={`achievement-card ${earned ? 'achievement-card--earned' : ''}`}>
      <div className="achievement-card__head">
        <span className="achievement-card__icon" aria-hidden="true">
          {earned ? <Icon size={22} /> : <Lock size={20} />}
        </span>
        <div className="achievement-card__titles">
          <div className="achievement-card__name">{achievement.name}</div>
          {achievement.description ? <div className="achievement-card__desc">{achievement.description}</div> : null}
        </div>
        <Badge tone={earned ? 'success' : 'neutral'}>{earned ? 'Получено' : 'В процессе'}</Badge>
      </div>
      {earned ? null : (
        <ProgressBar value={Math.min(progress, target)} max={target || 1} label={label} showValue tone="primary" />
      )}
      <div className="achievement-card__footer">
        <RewardChips rewards={{ coins: achievement.reward_coins, intelligence: achievement.reward_intelligence_points }} />
        {earned && earnedAt ? (
          <span className="achievement-card__date">
            {new Date(earnedAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' })}
          </span>
        ) : null}
      </div>
    </div>
  );
}
