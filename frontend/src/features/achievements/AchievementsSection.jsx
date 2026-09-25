import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppDispatch, useAppState } from '../../state/AppProvider.jsx';
import { getUserAchievements, listAchievements, checkAchievements } from '../../services/achievements.js';
import { AchievementsList } from './components/AchievementsList.jsx';
import { Modal } from '../../components/common/Modal.jsx';
import { Award } from 'lucide-react';
import { Button } from '../../components/ui/index.jsx';
import { RewardChips } from '../../components/ui/icons.jsx';

export function AchievementsSection({ isActive }) {
  const { user, achievementNotifications } = useAppState();
  const dispatch = useAppDispatch();

  const [achievements, setAchievements] = useState([]);
  const [userAchievementMap, setUserAchievementMap] = useState(() => new Map());
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isRewardsModalOpen, setRewardsModalOpen] = useState(false);

  const loadAchievements = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      // Сначала загружаем все достижения
      const allAchievements = await listAchievements();
      setAchievements(Array.isArray(allAchievements) ? allAchievements : []);
      
      // Получаем уникальные типы требований
      const requirementTypes = [...new Set(allAchievements.map(a => a.requirement_type))];
      
      // Проверяем все типы достижений для обновления прогресса
      for (const reqType of requirementTypes) {
        try {
          await checkAchievements(user.id, reqType);
        } catch (checkError) {
          console.warn(`Ошибка проверки достижений типа ${reqType}:`, checkError);
        }
      }
      
      // Загружаем обновленные данные достижений пользователя
      const userAchievements = await getUserAchievements(user.id);
      const map = new Map();
      (userAchievements || []).forEach((record) => {
        map.set(record.achievement_id, record);
      });
      setUserAchievementMap(map);
    } catch (loadError) {
      console.error('Ошибка загрузки достижений:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить достижения');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  useEffect(() => {
    if (isActive && user?.id) {
      loadAchievements();
    }
  }, [isActive, user?.id]); // Убрали loadAchievements из зависимостей

  const completedCount = useMemo(() => {
    let count = 0;
    userAchievementMap.forEach((record) => {
      if (record.completed) {
        count++;
      }
    });
    return count;
  }, [userAchievementMap]);
  const totalCount = achievements.length;

  useEffect(() => {
    if (isActive && achievementNotifications.length > 0) {
      setRewardsModalOpen(true);
    }
  }, [isActive, achievementNotifications.length]);

  useEffect(() => {
    if (!isActive) {
      setRewardsModalOpen(false);
    }
  }, [isActive]);

  const handleCloseRewardsModal = useCallback(() => {
    setRewardsModalOpen(false);
    dispatch({ type: 'CLEAR_ACHIEVEMENT_NOTIFICATIONS' });
  }, [dispatch]);

  const renderRewardRow = useCallback((notification) => {
    const {
      achievement_id: achievementId,
      achievement_name: achievementName,
      reward_coins: rewardCoins = 0,
      reward_intelligence_points: rewardIntelligencePoints = 0,
    } = notification;

    return (
      <div key={`${achievementId}-${notification.timestamp}`} className="achievement-reward-row">
        <div className="achievement-reward-title inline-icon">
          <Award size={18} className="stat-tone--coins" aria-hidden="true" />
          {achievementName ?? `Достижение #${achievementId}`}
        </div>
        <RewardChips rewards={{ coins: rewardCoins, intelligence: rewardIntelligencePoints }} />
      </div>
    );
  }, []);

  return (
    <div>
      <div className="section-header">
        <h2 className="inline-icon"><Award size={22} aria-hidden="true" /> Достижения</h2>
      </div>
      <div className="achievements-stats">
        <div className="stat-badge">
          <div className="badge-value" id="achievementsCompleted">
            {completedCount}
          </div>
          <div className="badge-label">Получено</div>
        </div>
        <div className="stat-badge">
          <div className="badge-value" id="achievementsTotal">
            {totalCount}
          </div>
          <div className="badge-label">Всего</div>
        </div>
      </div>

      <AchievementsList
        achievements={achievements}
        userAchievementMap={userAchievementMap}
        isLoading={isLoading}
        error={error}
        onRetry={loadAchievements}
      />

      <Modal
        isOpen={isRewardsModalOpen}
        onClose={handleCloseRewardsModal}
        title="Новое достижение!"
        footer={(
          <Button block onClick={handleCloseRewardsModal}>
            Отлично
          </Button>
        )}
      >
        <div className="achievement-reward-list">
          {achievementNotifications.map(renderRewardRow)}
        </div>
      </Modal>
    </div>
  );
}

