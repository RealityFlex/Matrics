import React from 'react';
import { AchievementCard } from './AchievementCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function AchievementsList({ achievements, userAchievementMap, isLoading, error, onRetry }) {
  if (isLoading) {
    return <StateView state="loading" message="Загружаем достижения…" />;
  }
  if (error) {
    return <StateView state="error" title="Не удалось загрузить достижения" message={error} onRetry={onRetry} />;
  }
  if (!achievements.length) {
    return <StateView state="empty" title="Достижений пока нет" />;
  }

  // Сначала полученные, затем — по близости к цели
  const sorted = [...achievements].sort((a, b) => {
    const ra = userAchievementMap.get(a.id);
    const rb = userAchievementMap.get(b.id);
    if (Boolean(ra?.completed) !== Boolean(rb?.completed)) return ra?.completed ? -1 : 1;
    const pa = (ra?.progress || 0) / (a.requirement_value || 1);
    const pb = (rb?.progress || 0) / (b.requirement_value || 1);
    return pb - pa;
  });

  return (
    <div className="achievements-grid" id="achievementsList">
      {sorted.map((achievement) => {
        const userAchievement = userAchievementMap.get(achievement.id);
        return (
          <AchievementCard
            key={achievement.id}
            achievement={achievement}
            earnedAt={userAchievement?.completed_at}
            isCompleted={userAchievement?.completed || false}
            progress={userAchievement?.progress || 0}
          />
        );
      })}
    </div>
  );
}
