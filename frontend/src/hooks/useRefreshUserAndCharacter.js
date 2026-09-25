import { useCallback } from 'react';
import { useAppDispatch, useAppState, persistUser } from '../state/AppProvider.jsx';
import { getUser } from '../services/users.js';
import { refreshCharacter } from '../services/characters.js';

export function useRefreshUserAndCharacter() {
  const { user } = useAppState();
  const dispatch = useAppDispatch();

  return useCallback(async () => {
    if (!user?.id) {
      return null;
    }
    const [freshUser, freshCharacter] = await Promise.all([getUser(user.id), refreshCharacter(user.id)]);
    dispatch({ type: 'SET_USER', user: freshUser });
    dispatch({ type: 'SET_CHARACTER', character: freshCharacter });
    persistUser(freshUser);
    return { user: freshUser, character: freshCharacter };
  }, [user?.id, dispatch]);
}

