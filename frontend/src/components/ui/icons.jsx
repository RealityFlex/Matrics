/**
 * Единая система иконок «Матрикс»: линейные SVG-иконки lucide (лицензия ISC)
 * вместо эмодзи. Показатели персонажа (монеты, интеллект, настроение…) имеют
 * закреплённые иконку и цвет — используйте StatIcon / StatValue / RewardChips,
 * а не отдельные иконки, чтобы смысл читался одинаково на всех экранах.
 */
import React from 'react';
import {
  Award,
  Brain,
  Coins,
  Flame,
  GraduationCap,
  Smile,
  Snowflake,
  Sparkles,
  Star
} from 'lucide-react';

export const STATS = {
  coins: { Icon: Coins, label: 'Монеты', tone: 'coins' },
  intelligence: { Icon: Brain, label: 'Интеллект', tone: 'intellect' },
  satisfaction: { Icon: Smile, label: 'Настроение', tone: 'mood' },
  experience: { Icon: Sparkles, label: 'Опыт', tone: 'xp' },
  level: { Icon: GraduationCap, label: 'Уровень', tone: 'intellect' },
  rating: { Icon: Star, label: 'Рейтинг', tone: 'coins' },
  streak: { Icon: Flame, label: 'Серия посещений', tone: 'streak' },
  freeze: { Icon: Snowflake, label: 'Заморозки', tone: 'info' },
  achievement: { Icon: Award, label: 'Достижение', tone: 'coins' }
};

/** Иконка показателя с закреплённым цветом. */
export function StatIcon({ kind, size = 16, className = '', title }) {
  const stat = STATS[kind];
  if (!stat) return null;
  const { Icon } = stat;
  return (
    <Icon
      size={size}
      strokeWidth={2}
      className={`ui-icon stat-tone--${stat.tone} ${className}`}
      aria-hidden={title ? undefined : true}
      aria-label={title}
      role={title ? 'img' : undefined}
    />
  );
}

/** «иконка + значение» с доступной подписью показателя. */
export function StatValue({ kind, value, size = 16, signed = false, className = '' }) {
  const stat = STATS[kind];
  const shown = signed && typeof value === 'number' && value > 0 ? `+${value}` : value;
  return (
    <span className={`ui-stat-value ${className}`} title={stat?.label}>
      <StatIcon kind={kind} size={size} />
      <span className="tabular">{shown}</span>
      {stat ? <span className="visually-hidden">{stat.label}</span> : null}
    </span>
  );
}

const REWARD_ORDER = ['coins', 'intelligence', 'satisfaction', 'experience'];

/**
 * Чипы наград: <RewardChips rewards={{ coins: 5, intelligence: 15, satisfaction: 8 }} />.
 * Нулевые и пустые значения не показываются.
 */
export function RewardChips({ rewards = {}, signed = true, size = 14, className = '' }) {
  const items = REWARD_ORDER.filter((kind) => rewards[kind]);
  if (!items.length) return null;
  return (
    <div className={`reward-chips ${className}`}>
      {items.map((kind) => (
        <span key={kind} className={`reward-chip reward-chip--${STATS[kind].tone}`}>
          <StatValue kind={kind} value={rewards[kind]} signed={signed} size={size} />
        </span>
      ))}
    </div>
  );
}
