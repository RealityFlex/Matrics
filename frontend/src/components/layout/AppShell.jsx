import React, { useEffect, useMemo, useState, useCallback } from 'react';
import { LoginScreen } from '../auth/LoginScreen.jsx';
import { AppLayout } from './AppLayout.jsx';
import { useAppDispatch, useAppState, clearPersistedUser, persistUser } from '../../state/AppProvider.jsx';
import { listUsers, createUser, getUser, authWithMax, joinByCode } from '../../services/users.js';
import { CuratorCabinet } from '../../features/curator/CuratorCabinet.jsx';
import { toast } from '../ui/toast.jsx';
import { createCharacter, ensureCharacter, getCharacterByUser } from '../../services/characters.js';
import { ConfirmModal } from '../common/ConfirmModal.jsx';
import { TodaySection } from '../../features/today/TodaySection.jsx';
import { TasksSection } from '../../features/tasks/TasksSection.jsx';
import { HabitsSection } from '../../features/habits/HabitsSection.jsx';
import { InventorySection } from '../../features/inventory/InventorySection.jsx';
import { ShopSection } from '../../features/shop/ShopSection.jsx';
import { AchievementsSection } from '../../features/achievements/AchievementsSection.jsx';
import { SocialSection } from '../../features/social/SocialSection.jsx';
import { EventsSection } from '../../features/events/EventsSection.jsx';
import { CompetitionsSection } from '../../features/competitions/CompetitionsSection.jsx';
import { StatsSection } from '../../features/stats/StatsSection.jsx';
import { useRealtimeUpdates } from '../../hooks/useRealtimeUpdates.js';
import { parseCheckinPayload } from '../../services/events.js';
import { getStartParam, getWebApp, readyAndExpand } from '../../utils/maxBridge.js';
import { Spinner } from '../ui/index.jsx';
import {
  Award,
  Backpack,
  BarChart3,
  CalendarDays,
  CircleCheckBig,
  Flag,
  GraduationCap,
  House,
  ListTodo,
  Store,
  Users
} from 'lucide-react';
import '../../styles/features-extra.css';

// Иконки навигации: lucide вместо эмодзи
const navIcon = (Icon) => <Icon size={22} strokeWidth={2} aria-hidden="true" />;

export function AppShell() {
  const { user, isBootstrapFinished } = useAppState();
  const dispatch = useAppDispatch();

  useRealtimeUpdates();

  const [isLoggingIn, setIsLoggingIn] = useState(false);
  const [isHydrating, setIsHydrating] = useState(false);
  const [isUserHydrated, setIsUserHydrated] = useState(false);
  const [loginError, setLoginError] = useState(null);
  const [maxAuthAttempted, setMaxAuthAttempted] = useState(false);
  const [showLogoutConfirm, setShowLogoutConfirm] = useState(false);

  const [pendingJoin, setPendingJoin] = useState(null);

  // Диплинки мини-приложения: att-<id>-<код> (отметка), join-/cur-<код> (вступление), curator, checkin, game
  useEffect(() => {
    const startParam = getStartParam() || '';
    if (/^(join|cur)-[A-Za-z0-9]{6,16}$/.test(startParam)) {
      setPendingJoin(startParam);
    } else if (startParam === 'curator') {
      dispatch({ type: 'SET_ACTIVE_SECTION', section: 'curator' });
    } else if (startParam === 'game') {
      dispatch({ type: 'SET_ACTIVE_SECTION', section: 'today' });
      dispatch({ type: 'SET_PENDING_GAME', value: true });
    }
    const payload = parseCheckinPayload(startParam);
    if (payload) {
      dispatch({ type: 'SET_PENDING_CHECKIN', value: payload });
      dispatch({ type: 'SET_ACTIVE_SECTION', section: 'today' });
      try {
        const url = new URL(window.location.href);
        if (url.searchParams.has('startapp')) {
          url.searchParams.delete('startapp');
          window.history.replaceState(null, '', url.toString());
        }
      } catch {
        /* адресная строка недоступна внутри MAX — не критично */
      }
    }
  }, [dispatch]);

  const handleMaxLogin = useCallback(async () => {
    setLoginError(null);
    setIsLoggingIn(true);
    try {
      const initData = getWebApp()?.initData;
      if (!initData) {
        throw new Error('MAX не передал данные запуска. Откройте мини-приложение из чата с ботом.');
      }
      // Сервер проверяет подпись initData и находит/создаёт пользователя (со стартовыми предметами и персонажем)
      const { user: authUser } = await authWithMax(initData);
      const [freshUser, character] = await Promise.all([getUser(authUser.id), ensureCharacter(authUser.id, authUser.username)]);

      dispatch({ type: 'SET_USER', user: freshUser });
      dispatch({ type: 'SET_CHARACTER', character });
      dispatch({ type: 'SET_ACTIVE_SECTION', section: 'today' });

      persistUser(freshUser);
      setIsUserHydrated(true);
    } catch (error) {
      console.error('Ошибка авторизации через MAX:', error);
      setLoginError(error.message ?? 'Не удалось выполнить автоматический вход');
    } finally {
      setIsLoggingIn(false);
      readyAndExpand();
    }
  }, [dispatch]);

  // Автоматическая авторизация через MAX Bridge
  useEffect(() => {
    if (!isBootstrapFinished || user || maxAuthAttempted) {
      return;
    }

    // Функция для проверки и авторизации через MAX
    const checkMaxAuth = () => {
      // Проверяем наличие MAX Bridge
      if (typeof window !== 'undefined' && window.WebApp) {
        // Проверяем initDataUnsafe (небезопасные данные, но достаточные для авторизации)
        if (window.WebApp.initData || window.WebApp.initDataUnsafe?.user?.id) {
          setMaxAuthAttempted(true);
          handleMaxLogin();
          return true;
        }
        // Если WebApp есть, но данных нет - помечаем попытку
        setMaxAuthAttempted(true);
        return false;
      }
      return false;
    };

    // Пытаемся сразу проверить
    if (checkMaxAuth()) {
      return;
    }

    // Если MAX Bridge еще не загружен, ждем немного и проверяем снова
    let attempts = 0;
    const maxAttempts = 10; // 10 попыток по 100мс = 1 секунда
    const checkInterval = setInterval(() => {
      attempts++;
      if (checkMaxAuth() || attempts >= maxAttempts) {
        clearInterval(checkInterval);
        if (attempts >= maxAttempts && !maxAuthAttempted) {
          // Если после всех попыток MAX Bridge не найден, помечаем попытку
          setMaxAuthAttempted(true);
        }
      }
    }, 100);

    return () => {
      clearInterval(checkInterval);
    };
  }, [isBootstrapFinished, user, maxAuthAttempted, handleMaxLogin]);

  // Вступление в группу / роль куратора по ссылке — после входа пользователя
  useEffect(() => {
    if (!pendingJoin || !user?.id || !isUserHydrated) return;
    setPendingJoin(null);
    joinByCode(user.id, pendingJoin)
      .then(async (result) => {
        const org = result.organization?.short_name ? ` · ${result.organization.short_name}` : '';
        toast.success(result.kind === 'curator' ? 'Вы куратор группы' : 'Добро пожаловать в группу!', `${result.group.name}${org}`);
        const freshUser = await getUser(user.id);
        dispatch({ type: 'SET_USER', user: freshUser });
        if (result.kind === 'curator') dispatch({ type: 'SET_ACTIVE_SECTION', section: 'curator' });
      })
      .catch((error) => toast.error('Приглашение не сработало', error?.message));
  }, [pendingJoin, user?.id, isUserHydrated, dispatch]);

  const isStaff = user?.role === 'curator' || user?.role === 'admin';

  const sections = useMemo(
    () => [
      ...(isStaff ? [{ id: 'curator', label: 'Группы', icon: navIcon(GraduationCap), domId: 'curatorSection', component: CuratorCabinet }] : []),
      { id: 'today', label: 'Сегодня', icon: navIcon(House), domId: 'todaySection', component: TodaySection },
      { id: 'tasks', label: 'Задачи', icon: navIcon(ListTodo), domId: 'tasksSection', component: TasksSection },
      { id: 'habits', label: 'Привычки', icon: navIcon(CircleCheckBig), domId: 'habitsSection', component: HabitsSection },
      { id: 'inventory', label: 'Инвентарь', icon: navIcon(Backpack), domId: 'inventorySection', component: InventorySection },
      { id: 'shop', label: 'Магазин', icon: navIcon(Store), domId: 'shopSection', component: ShopSection },
      { id: 'achievements', label: 'Достижения', icon: navIcon(Award), domId: 'achievementsSection', component: AchievementsSection },
      { id: 'social', label: 'Социальное', icon: navIcon(Users), domId: 'socialSection', component: SocialSection },
      { id: 'events', label: 'События', icon: navIcon(CalendarDays), domId: 'eventsSection', component: EventsSection },
      { id: 'competitions', label: 'Соревнования', icon: navIcon(Flag), domId: 'competitionsSection', component: CompetitionsSection },
      { id: 'stats', label: 'Статистика', icon: navIcon(BarChart3), domId: 'statsSection', component: StatsSection }
    ],
    [isStaff]
  );

  useEffect(() => {
    if (!isBootstrapFinished || !user?.id || isUserHydrated) {
      return;
    }

    let canceled = false;

    async function hydrateUser() {
      setIsHydrating(true);
      try {
        const fullUser = await getUser(user.id);
        const character = await ensureCharacter(user.id, fullUser.username);
        if (canceled) {
          return;
        }
        dispatch({ type: 'SET_USER', user: fullUser });
        dispatch({ type: 'SET_CHARACTER', character });
        persistUser(fullUser);
        setIsUserHydrated(true);
      } catch (error) {
        console.error('Ошибка загрузки пользователя:', error);
        if (!canceled) {
          setLoginError(error.message ?? 'Не удалось загрузить данные пользователя');
          clearPersistedUser();
          dispatch({ type: 'RESET' });
          setIsUserHydrated(false);
        }
      } finally {
        if (!canceled) {
          setIsHydrating(false);
        }
      }
    }

    hydrateUser();

    return () => {
      canceled = true;
    };
  }, [isBootstrapFinished, user?.id, isUserHydrated, dispatch]);

  const handleLogin = async (username) => {
    setLoginError(null);
    setIsLoggingIn(true);
    try {
      const users = await listUsers();
      let foundUser = users.find((candidate) => candidate.username === username);

      if (!foundUser) {
        foundUser = await createUser({
          username,
          email: `${username}@tamagotchi.local`
        });
      }

      let character = null;
      try {
        character = await getCharacterByUser(foundUser.id);
      } catch (error) {
        const message = error?.message ?? '';
        if (error?.status === 404 || message.includes('404')) {
          await createCharacter({
            user_id: foundUser.id,
            name: `${foundUser.username}'s Hero`
          });
          character = await getCharacterByUser(foundUser.id);
        } else {
          throw error;
        }
      }

      const freshUser = await getUser(foundUser.id);

      dispatch({ type: 'SET_USER', user: freshUser });
      dispatch({ type: 'SET_CHARACTER', character });
      dispatch({ type: 'SET_ACTIVE_SECTION', section: 'today' });

      persistUser(freshUser);
      setIsUserHydrated(true);
    } catch (error) {
      console.error('Ошибка входа:', error);
      setLoginError(error.message ?? 'Не удалось выполнить вход');
    } finally {
      setIsLoggingIn(false);
    }
  };

  const handleLogout = () => {
    setShowLogoutConfirm(true);
  };

  const handleLogoutConfirm = () => {
    clearPersistedUser();
    dispatch({ type: 'RESET' });
    setIsUserHydrated(false);
    setShowLogoutConfirm(false);
  };

  // Показываем экран логина только если:
  // 1. Пользователь не авторизован
  // 2. MAX авторизация не выполняется
  // 3. Попытка MAX авторизации завершена (не удалась или MAX Bridge недоступен)
  if (!user && isLoggingIn && maxAuthAttempted) {
    return (
      <div className="screen active screen--center">
        <Spinner size="lg" label="Входим через MAX…" />
      </div>
    );
  }

  if (!user && (!isLoggingIn || maxAuthAttempted)) {
    return <LoginScreen onLogin={handleLogin} isLoading={isLoggingIn} error={loginError} />;
  }

  // Показываем загрузку во время автоматической авторизации через MAX
  if (!user && isLoggingIn && !maxAuthAttempted) {
    return (
      <div className="screen active screen--center">
        <Spinner size="lg" label="Входим через MAX…" />
      </div>
    );
  }

  if (isHydrating && !isUserHydrated) {
    return (
      <div className="screen active screen--center">
        <Spinner size="lg" label="Загружаем персонажа…" />
      </div>
    );
  }

  return (
    <>
      <AppLayout sections={sections} onLogout={handleLogout} />
      <ConfirmModal
        isOpen={showLogoutConfirm}
        onClose={() => setShowLogoutConfirm(false)}
        onConfirm={handleLogoutConfirm}
        title="Выход из аккаунта"
        message="Вы уверены, что хотите выйти?"
        confirmText="Выйти"
        cancelText="Отмена"
        type="warning"
      />
    </>
  );
}

