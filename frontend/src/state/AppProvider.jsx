import React, { createContext, useContext, useEffect, useMemo, useReducer } from 'react';

const STORAGE_KEYS = {
  userId: 'currentUserId',
  username: 'currentUsername'
};

const AppStateContext = createContext(null);
const AppDispatchContext = createContext(null);

const initialState = {
  isBootstrapFinished: false,
  user: null,
  character: null,
  dailyReward: {
    isClaimed: false,
    nextAvailableAt: null,
    isLoading: false,
    error: null
  },
  activeSection: 'today',
  // Отметка из QR-диплинка (?startapp=att-<id>-<код>), ожидающая выполнения на экране «Сегодня»
  pendingCheckIn: null,
  // Открыть мини-игру сразу после входа (?startapp=game — кнопка из бота)
  pendingGame: false,
  userCache: {},
  modals: {
    more: false
  },
  badges: {},
  achievementNotifications: [],
  inventorySyncVersion: 0
};

function appReducer(state, action) {
  switch (action.type) {
    case 'SET_BOOTSTRAP_FINISHED':
      return { ...state, isBootstrapFinished: true };
    case 'SET_USER':
      return { ...state, user: action.user };
    case 'SET_CHARACTER':
      return { ...state, character: action.character };
    case 'MERGE_CHARACTER':
      return state.character ? { ...state, character: { ...state.character, ...action.patch } } : state;
    case 'SET_PENDING_CHECKIN':
      return { ...state, pendingCheckIn: action.value };
    case 'SET_PENDING_GAME':
      return { ...state, pendingGame: Boolean(action.value) };
    case 'SET_DAILY_REWARD':
      return { ...state, dailyReward: { ...state.dailyReward, ...action.payload } };
    case 'SET_DAILY_REWARD_LOADING':
      return {
        ...state,
        dailyReward: {
          ...state.dailyReward,
          isLoading: action.value,
          error: action.error ?? state.dailyReward.error
        }
      };
    case 'SET_ACTIVE_SECTION':
      return { ...state, activeSection: action.section };
    case 'TOGGLE_MODAL':
      return {
        ...state,
        modals: { ...state.modals, [action.modal]: action.value }
      };
    case 'SET_BADGE':
      return {
        ...state,
        badges: {
          ...state.badges,
          [action.key]: action.value ?? true
        }
      };
    case 'CLEAR_BADGE': {
      const { [action.key]: _removed, ...restBadges } = state.badges;
      return {
        ...state,
        badges: restBadges
      };
    }
    case 'CACHE_USER':
      return {
        ...state,
        userCache: {
          ...state.userCache,
          [action.userId]: action.payload
        }
      };
    case 'RESET':
      return { ...initialState, isBootstrapFinished: true };
    case 'ADD_ACHIEVEMENT_NOTIFICATION':
      return {
        ...state,
        achievementNotifications: [
          ...state.achievementNotifications,
          {
            id: action.payload?.achievement_id ?? Date.now(),
            timestamp: Date.now(),
            ...action.payload
          }
        ]
      };
    case 'CLEAR_ACHIEVEMENT_NOTIFICATIONS':
      return {
        ...state,
        achievementNotifications: []
      };
    case 'INVENTORY_EVENT':
      return {
        ...state,
        inventorySyncVersion: state.inventorySyncVersion + 1
      };
    default:
      return state;
  }
}

export function AppProvider({ children }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  useEffect(() => {
    const storedUserIdRaw = localStorage.getItem(STORAGE_KEYS.userId);
    const storedUserId = storedUserIdRaw ? Number(storedUserIdRaw) : null;
    const storedUsername = localStorage.getItem(STORAGE_KEYS.username);

    if (storedUserId && storedUsername) {
      dispatch({
        type: 'SET_USER',
        user: {
          id: storedUserId,
          username: storedUsername
        }
      });
    }

    dispatch({ type: 'SET_BOOTSTRAP_FINISHED' });
  }, []);

  const value = useMemo(() => state, [state]);

  return (
    <AppStateContext.Provider value={value}>
      <AppDispatchContext.Provider value={dispatch}>{children}</AppDispatchContext.Provider>
    </AppStateContext.Provider>
  );
}

export function useAppState() {
  const context = useContext(AppStateContext);
  if (context === null) {
    throw new Error('useAppState должен использоваться внутри AppProvider');
  }
  return context;
}

export function useAppDispatch() {
  const context = useContext(AppDispatchContext);
  if (context === null) {
    throw new Error('useAppDispatch должен использоваться внутри AppProvider');
  }
  return context;
}

export function persistUser(user) {
  if (user?.id) {
    localStorage.setItem(STORAGE_KEYS.userId, String(user.id));
    if (user.username) {
      localStorage.setItem(STORAGE_KEYS.username, user.username);
    }
  }
}

export function clearPersistedUser() {
  localStorage.removeItem(STORAGE_KEYS.userId);
  localStorage.removeItem(STORAGE_KEYS.username);
}

