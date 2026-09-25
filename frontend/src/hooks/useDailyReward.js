import { useCallback, useEffect, useMemo, useState } from 'react';
import { useAppDispatch, useAppState } from '../state/AppProvider.jsx';
import { getApiBase } from '../services/apiClient.js';
import { toast } from '../components/ui/toast.jsx';

const DAILY_REWARD_STORAGE_KEY = 'dailyRewardCache';

function loadDailyCache(userId) {
  try {
    const raw = localStorage.getItem(`${DAILY_REWARD_STORAGE_KEY}:${userId}`);
    if (!raw) {
      return null;
    }
    const cached = JSON.parse(raw);
    if (cached.nextAvailableAt) {
      try {
        const nextDate = new Date(cached.nextAvailableAt);
        if (Date.now() >= nextDate.getTime()) {
          localStorage.removeItem(`${DAILY_REWARD_STORAGE_KEY}:${userId}`);
          return null;
        }
      } catch {
        localStorage.removeItem(`${DAILY_REWARD_STORAGE_KEY}:${userId}`);
        return null;
      }
    }
    return cached;
  } catch {
    return null;
  }
}

function persistDailyCache(userId, payload) {
  try {
    if (userId) {
      localStorage.setItem(`${DAILY_REWARD_STORAGE_KEY}:${userId}`, JSON.stringify(payload));
    }
  } catch {
    // ignore
  }
}

// Уведомления — через общий механизм тостов (раньше была отдельная модалка useNotification)
const NOTIFY = {
  success: (message) => toast.reward('Ежедневный подарок', message),
  info: (message) => toast.info('Ежедневный подарок', message),
  error: (message) => toast.error('Ежедневный подарок', message)
};

export function useDailyReward({ autoFetch = false, silent = false } = {}) {
  const { user, dailyReward } = useAppState();
  const dispatch = useAppDispatch();
  const notify = NOTIFY;

  const userId = user?.id ?? null;
  const [isClaiming, setIsClaiming] = useState(false);

  const dailyState = useMemo(() => {
    if (!userId) {
      return {
        isClaimed: false,
        nextAvailableAt: null,
        isLoading: false,
        error: null
      };
    }
    if (dailyReward && dailyReward.nextAvailableAt !== undefined) {
      return dailyReward;
    }
    const cached = loadDailyCache(userId);
    if (cached) {
      return {
        isClaimed: Boolean(cached.isClaimed),
        nextAvailableAt: cached.nextAvailableAt ? new Date(cached.nextAvailableAt).toISOString() : null,
        isLoading: false,
        error: null
      };
    }
    return {
      isClaimed: false,
      nextAvailableAt: null,
      isLoading: false,
      error: null
    };
  }, [dailyReward, userId]);

  useEffect(() => {
    if (!autoFetch || !userId) {
      return;
    }

    let canceled = false;

    async function checkDailyRewardStatus() {
      try {
        const response = await fetch(`${getApiBase()}/users/${userId}/daily-reward`, {
          method: 'GET',
          headers: { 'Content-Type': 'application/json' }
        });

        if (canceled) {
          return;
        }

        if (response.ok) {
          const payload = await response.json();
          const isAvailable = Boolean(payload?.success);
          const nextAvailableAt = payload?.next_available_at || payload?.nextAvailableAt || null;
          dispatch({
            type: 'SET_DAILY_REWARD',
            payload: {
              isClaimed: !isAvailable,
              nextAvailableAt,
              error: null
            }
          });
          persistDailyCache(userId, {
            isClaimed: !isAvailable,
            nextAvailableAt
          });
        } else {
          const cached = loadDailyCache(userId);
          if (cached) {
            dispatch({
              type: 'SET_DAILY_REWARD',
              payload: {
                isClaimed: Boolean(cached.isClaimed),
                nextAvailableAt: cached.nextAvailableAt ? new Date(cached.nextAvailableAt).toISOString() : null,
                error: null
              }
            });
          } else {
            dispatch({
              type: 'SET_DAILY_REWARD',
              payload: {
                isClaimed: false,
                nextAvailableAt: null,
                error: null
              }
            });
          }
        }
      } catch (error) {
        console.error('Ошибка проверки статуса ежедневного подарка:', error);
        if (!canceled) {
          const cached = loadDailyCache(userId);
          if (cached) {
            dispatch({
              type: 'SET_DAILY_REWARD',
              payload: {
                isClaimed: Boolean(cached.isClaimed),
                nextAvailableAt: cached.nextAvailableAt ? new Date(cached.nextAvailableAt).toISOString() : null,
                error: null
              }
            });
          } else {
            dispatch({
              type: 'SET_DAILY_REWARD',
              payload: {
                isClaimed: false,
                nextAvailableAt: null,
                error: null
              }
            });
          }
        }
      }
    }

    checkDailyRewardStatus();
    const interval = setInterval(checkDailyRewardStatus, 5 * 60 * 1000);

    return () => {
      canceled = true;
      clearInterval(interval);
    };
  }, [autoFetch, dispatch, userId]);

  const handleClaimDailyReward = useCallback(async () => {
    if (!userId || isClaiming) {
      return;
    }

    setIsClaiming(true);
    dispatch({ type: 'SET_DAILY_REWARD_LOADING', value: true, error: null });
    try {
      const response = await fetch(`${getApiBase()}/users/${userId}/daily-reward`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
      });

      let payload = null;
      if (response.ok) {
        payload = await response.json();
      } else {
        const text = await response.text();
        try {
          payload = JSON.parse(text);
        } catch {
          payload = { detail: text };
        }
      }

      if (!response.ok) {
        const errorMessage = payload?.detail || 'Не удалось получить ежедневный подарок';
        if (!silent) {
          notify.error(errorMessage);
        }
        dispatch({ type: 'SET_DAILY_REWARD_LOADING', value: false, error: errorMessage });
        setIsClaiming(false);
        return;
      }

      const isClaimed = Boolean(payload?.success);
      const nextAvailableAt = payload?.next_available_at || payload?.nextAvailableAt || null;
      dispatch({
        type: 'SET_DAILY_REWARD',
        payload: {
          isClaimed,
          nextAvailableAt,
          error: null
        }
      });

      persistDailyCache(userId, {
        isClaimed,
        nextAvailableAt
      });

      if (isClaimed && !silent) {
        notify.success(`Получено монет: ${payload?.coins_added ?? 10}`);
      } else if (!silent) {
        const nextTime = nextAvailableAt;
        if (nextTime) {
          const nextDate = new Date(nextTime);
          notify.info(`Подарок уже получен. Попробуйте после ${nextDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`);
        } else {
          notify.info('Подарок сегодня уже получен.');
        }
      }

      if (isClaimed && payload?.coins_added) {
        dispatch({
          type: 'SET_USER',
          user: {
            ...(user || {}),
            id: userId,
            username: user?.username ?? null,
            coins: (user?.coins ?? 0) + (payload?.coins_added ?? 10)
          }
        });
      }

      dispatch({ type: 'SET_DAILY_REWARD_LOADING', value: false, error: null });
    } catch (error) {
      console.error('Ошибка получения ежедневного подарка:', error);
      const message = error?.message || 'Не удалось получить подарок';
      if (!silent) {
        notify.error(message);
      }
      dispatch({ type: 'SET_DAILY_REWARD_LOADING', value: false, error: message });
    } finally {
      setIsClaiming(false);
    }
  }, [dispatch, isClaiming, notify, silent, user, userId]);

  const isButtonDisabled = useMemo(() => {
    if (!userId) {
      return true;
    }
    if (dailyState.isLoading || isClaiming) {
      return true;
    }
    if (dailyState.isClaimed) {
      return true;
    }
    return false;
  }, [dailyState.isClaimed, dailyState.isLoading, isClaiming, userId]);

  const nextAvailableHint = useMemo(() => {
    if (!dailyState.nextAvailableAt) {
      return null;
    }
    try {
      const nextDate = new Date(dailyState.nextAvailableAt);
      return `Доступно после ${nextDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`;
    } catch {
      return null;
    }
  }, [dailyState.nextAvailableAt]);

  return {
    dailyState,
    isClaiming,
    handleClaimDailyReward,
    isButtonDisabled,
    nextAvailableHint
  };
}

