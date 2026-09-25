import { useEffect, useRef } from 'react';
import { useAppDispatch, useAppState, persistUser } from '../state/AppProvider.jsx';
import { getApiBase } from '../services/apiClient.js';

function buildRealtimeUrl(userId) {
  if (typeof window === 'undefined') {
    return null;
  }

  // Для WebSocket используем напрямую window.location.origin, так как путь /ws не связан с /api
  let baseUrl;
  try {
    baseUrl = new URL(window.location.origin);
  } catch (error) {
    console.warn('Не удалось разобрать origin для realtime URL:', error);
    return null;
  }

  baseUrl.pathname = `/ws/${userId}`;
  baseUrl.search = '';
  baseUrl.hash = '';
  baseUrl.protocol = baseUrl.protocol === 'https:' ? 'wss:' : 'ws:';

  return baseUrl.toString();
}

export function useRealtimeUpdates() {
  const { user, character, activeSection } = useAppState();
  const dispatch = useAppDispatch();

  const socketRef = useRef(null);
  const reconnectTimerRef = useRef(null);
  const currentUserRef = useRef(user);
  const currentCharacterRef = useRef(character);
  const currentActiveSectionRef = useRef(activeSection);

  useEffect(() => {
    currentUserRef.current = user;
  }, [user]);

  useEffect(() => {
    currentCharacterRef.current = character;
  }, [character]);

  useEffect(() => {
    currentActiveSectionRef.current = activeSection;
  }, [activeSection]);

  useEffect(() => {
    if (!user?.id) {
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      return undefined;
    }

    let closedByHook = false;
    let reconnectDelay = 1000;

    const scheduleReconnect = () => {
      if (closedByHook) {
        return;
      }
      const delay = reconnectDelay + Math.random() * 200;
      reconnectTimerRef.current = setTimeout(() => {
        reconnectTimerRef.current = null;
        reconnectDelay = Math.min(reconnectDelay * 2, 30000);
        connect();
      }, delay);
    };

    const handleParametersUpdate = (payload) => {
      if (!payload || typeof payload !== 'object') {
        return;
      }

      const currentUser = currentUserRef.current;
      if (currentUser && payload.coins !== undefined) {
        const updatedUser = { ...currentUser, coins: payload.coins };
        dispatch({ type: 'SET_USER', user: updatedUser });
        persistUser(updatedUser);
      }

      const currentCharacter = currentCharacterRef.current;
      if (currentCharacter) {
        let shouldUpdate = false;
        const updatedCharacter = { ...currentCharacter };

        if (payload.satisfaction !== undefined && payload.satisfaction !== currentCharacter.satisfaction) {
          updatedCharacter.satisfaction = payload.satisfaction;
          shouldUpdate = true;
        }
        if (
          payload.intelligence_level !== undefined &&
          payload.intelligence_level !== currentCharacter.intelligence_level
        ) {
          updatedCharacter.intelligence_level = payload.intelligence_level;
          shouldUpdate = true;
        }
        if (
          payload.intelligence_points !== undefined &&
          payload.intelligence_points !== currentCharacter.intelligence_points
        ) {
          updatedCharacter.intelligence_points = payload.intelligence_points;
          shouldUpdate = true;
        }
        if (payload.rating !== undefined && payload.rating !== currentCharacter.rating) {
          updatedCharacter.rating = payload.rating;
          shouldUpdate = true;
        }

        if (shouldUpdate) {
          dispatch({ type: 'SET_CHARACTER', character: updatedCharacter });
        }
      }
    };

    const toggleBadgeForSection = (sectionId, shouldSet = true) => {
      if (!sectionId) {
        return;
      }
      if (shouldSet) {
        if (currentActiveSectionRef.current === sectionId) {
          dispatch({ type: 'CLEAR_BADGE', key: sectionId });
        } else {
          dispatch({ type: 'SET_BADGE', key: sectionId, value: true });
        }
      } else {
        dispatch({ type: 'CLEAR_BADGE', key: sectionId });
      }
    };

    const handleFriendRequestIncoming = () => {
      if (currentActiveSectionRef.current === 'social') {
        dispatch({ type: 'CLEAR_BADGE', key: 'social' });
      } else {
        dispatch({ type: 'SET_BADGE', key: 'social', value: true });
      }
    };

    const bumpInventorySync = () => {
      dispatch({ type: 'INVENTORY_EVENT' });
    };

    const handleTradeRequestIncoming = () => {
      toggleBadgeForSection('inventory', true);
      bumpInventorySync();
    };

    const handleTradeUpdated = () => {
      bumpInventorySync();
    };

    const handleAchievementCompleted = (payload) => {
      if (currentActiveSectionRef.current === 'achievements') {
        dispatch({ type: 'CLEAR_BADGE', key: 'achievements' });
      } else {
        dispatch({ type: 'SET_BADGE', key: 'achievements', value: true });
      }
      dispatch({
        type: 'ADD_ACHIEVEMENT_NOTIFICATION',
        payload,
      });
    };

    const handleCompetitionEvent = () => {
      toggleBadgeForSection('competitions', true);
    };

    const connect = () => {
      const url = buildRealtimeUrl(user.id);
      if (!url) {
        return;
      }

      const socket = new WebSocket(url);
      socketRef.current = socket;

      socket.onopen = () => {
        reconnectDelay = 1000;
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (!data?.type) {
            return;
          }
          if (data.type === 'parameters.updated') {
            handleParametersUpdate(data.payload);
            return;
          }
          if (data.type === 'social.friend_request.received') {
            handleFriendRequestIncoming();
            return;
          }
          if (data.type === 'achievements.completed') {
            handleAchievementCompleted(data.payload || {});
            return;
          }
          if (data.type === 'inventory.trade.received') {
            handleTradeRequestIncoming();
            return;
          }
          if (data.type === 'inventory.trade.updated') {
            handleTradeUpdated();
            return;
          }
          if (data.type === 'attendance.confirmed') {
            // Отметка могла прийти из чат-бота или с другого устройства — обновляем «Сегодня»
            const nextSatisfaction = data.payload?.character?.satisfaction;
            if (typeof nextSatisfaction === 'number') {
              dispatch({ type: 'MERGE_CHARACTER', patch: { satisfaction: nextSatisfaction } });
            }
            window.dispatchEvent(new CustomEvent('matrix:attendance', { detail: data.payload }));
            return;
          }
          if (data.type === 'appearance.changed') {
            const { active_character_set, active_environment_set } = data.payload || {};
            dispatch({ type: 'MERGE_CHARACTER', patch: { active_character_set, active_environment_set } });
            return;
          }
          if (
            data.type === 'competitions.challenge.invited' ||
            data.type === 'competitions.competition.announced'
          ) {
            handleCompetitionEvent();
          }
        } catch (error) {
          console.warn('Ошибка обработки события realtime:', error);
        }
      };

      socket.onclose = () => {
        socketRef.current = null;
        if (!closedByHook) {
          scheduleReconnect();
        }
      };

      socket.onerror = () => {
        socket.close();
      };
    };

    connect();

    return () => {
      closedByHook = true;
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (socketRef.current) {
        socketRef.current.close();
        socketRef.current = null;
      }
    };
  }, [user?.id, dispatch]);

  return null;
}


