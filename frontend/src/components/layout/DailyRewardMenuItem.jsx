import React, { useEffect } from 'react';
import { useAppDispatch } from '../../state/AppProvider.jsx';
import { useDailyReward } from '../../hooks/useDailyReward.js';
import { Gift } from 'lucide-react';

export function DailyRewardMenuItem({ onSelect }) {
  const dispatch = useAppDispatch();
  const { dailyState, isButtonDisabled, nextAvailableHint, handleClaimDailyReward, isClaiming } =
    useDailyReward({ autoFetch: false });

  useEffect(() => {
    if (!isButtonDisabled) {
      dispatch({ type: 'SET_BADGE', key: 'dailyReward' });
    } else {
      dispatch({ type: 'CLEAR_BADGE', key: 'dailyReward' });
    }
  }, [dispatch, isButtonDisabled]);

  const handleClick = async () => {
    if (isButtonDisabled) {
      return;
    }
    await handleClaimDailyReward();
    if (typeof onSelect === 'function') {
      onSelect();
    }
  };

  const hint = dailyState.error
    ? `Ошибка: ${dailyState.error}`
    : nextAvailableHint ?? 'Доступно раз в день';

  return (
    <button
      type="button"
      className={`menu-item daily-reward-menu-item ${isButtonDisabled ? 'menu-item--disabled' : ''}`}
      onClick={handleClick}
      disabled={isButtonDisabled || isClaiming}
    >
      {!isButtonDisabled ? <span className="badge-dot badge-dot--menu" aria-hidden="true" /> : null}
      <span className="menu-icon">
        <Gift size={22} strokeWidth={2} aria-hidden="true" />
      </span>
      <span className="menu-label-group">
        <span className="menu-label">Ежедневный подарок</span>
        <span className="menu-hint">{isClaiming ? 'Получаем…' : hint}</span>
      </span>
    </button>
  );
}

