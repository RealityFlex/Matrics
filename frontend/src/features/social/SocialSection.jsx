import React, { useCallback, useEffect, useState, useRef, useMemo } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import {
  listFriends,
  listGroups,
  getAllUsers,
  sendFriendRequest,
  acceptFriendRequest,
  removeFriendship,
  createGroup,
  inviteUserToGroup,
  getGroupInvitations,
  acceptGroupInvitation,
  rejectGroupInvitation,
  deleteGroup,
  removeGroupMember,
  getGroupMembers,
  getFriendStatistics,
  searchFriendCandidates
} from '../../services/social.js';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Modal } from '../../components/common/Modal.jsx';
import { Badge, Button, Spinner, StateView } from '../../components/ui/index.jsx';
import { StatIcon } from '../../components/ui/icons.jsx';
import {
  Backpack,
  BarChart3,
  CalendarCheck,
  Check,
  Flag,
  ListChecks,
  Plus,
  RefreshCw,
  Repeat,
  Search,
  Trash2,
  TrendingUp,
  UserMinus,
  UserPlus,
  Users,
  X
} from 'lucide-react';
import '../../styles/features-extra.css';

const FRIEND_STATUS = {
  pending: { label: 'Ожидает подтверждения', tone: 'warning' },
  accepted: { label: 'В друзьях', tone: 'success' },
  blocked: { label: 'Заблокирован', tone: 'danger' }
};

const INVITATION_STATUS = {
  pending: 'Ожидает ответа',
  accepted: 'Принято',
  rejected: 'Отклонено',
  declined: 'Отклонено',
  expired: 'Истекло'
};

function SectionBlock({ title, isLoading, error, items, renderItem, emptyText, onRetry }) {
  const hasItems = Array.isArray(items) && items.length > 0;
  return (
    <div className="social-block">
      {title ? <h3 className="section-subtitle">{title}</h3> : null}
      {isLoading ? (
        <StateView state="loading" compact />
      ) : error ? (
        <StateView state="error" title="Не удалось загрузить" message={error} onRetry={onRetry} compact />
      ) : !hasItems ? (
        <StateView state="empty" title={emptyText} compact />
      ) : (
        <div className="cards-list">{items.map(renderItem)}</div>
      )}
    </div>
  );
}

/** Сводка по другу: плитки «иконка + подпись + значение» без эмодзи */
function FriendStats({ stats }) {
  const tiles = [];
  const add = (key, icon, label, value) => tiles.push({ key, icon, label, value });
  if (stats.character && !stats.character.error) {
    add('mood', <StatIcon kind="satisfaction" size={16} />, 'Настроение', formatValue(stats.character.satisfaction, 0));
    add('coins', <StatIcon kind="coins" size={16} />, 'Монеты', formatValue(stats.character.coins, 0));
    add('rating', <StatIcon kind="rating" size={16} />, 'Рейтинг', formatValue(stats.character.rating, 0));
    if (stats.character.intelligence_level !== undefined) {
      add('level', <StatIcon kind="intelligence" size={16} />, 'Уровень интеллекта', formatValue(stats.character.intelligence_level, 0));
    }
  }
  if (stats.tasks && !stats.tasks.error) {
    add('tasks', <ListChecks size={16} aria-hidden="true" />, 'Задачи', `${formatValue(stats.tasks.completed, 0)} / ${formatValue(stats.tasks.total, 0)}`);
    if (stats.tasks.completion_rate !== undefined) {
      add('rate', <TrendingUp size={16} aria-hidden="true" />, 'Доля выполненных', `${formatValue(stats.tasks.completion_rate, 0)}%`);
    }
  }
  if (stats.habits && !stats.habits.error) {
    add('habits', <Repeat size={16} aria-hidden="true" />, 'Привычки', `${formatValue(stats.habits.total_completions, 0)} / ${formatValue(stats.habits.total_habits, 0)}`);
  }
  if (stats.inventory && !stats.inventory.error) {
    add('inventory', <Backpack size={16} aria-hidden="true" />, 'Предметы', formatValue(stats.inventory.total_items, 0));
  }
  if (stats.achievements && !stats.achievements.error) {
    add('achievements', <StatIcon kind="achievement" size={16} />, 'Достижения', `${formatValue(stats.achievements.completed, 0)} / ${formatValue(stats.achievements.total_achievements, 0)}`);
  }
  if (stats.events && !stats.events.error) {
    add('events', <CalendarCheck size={16} aria-hidden="true" />, 'Посещено событий', formatValue(stats.events.attended_events, 0));
  }
  if (stats.competitions && !stats.competitions.error) {
    add('competitions', <Flag size={16} aria-hidden="true" />, 'Соревнования', formatValue(stats.competitions.completed_competitions, 0));
  }
  if (!tiles.length) return <div className="social-muted">Статистика недоступна</div>;
  return (
    <div className="social-stats">
      {tiles.map((tile) => (
        <div key={tile.key} className="social-stats__item">
          <span className="social-stats__icon">{tile.icon}</span>
          <span className="social-stats__label">{tile.label}</span>
          <span className="social-stats__value tabular">{tile.value}</span>
        </div>
      ))}
    </div>
  );
}

function formatValue(value, fallback = '—') {
  if (value === null || value === undefined) {
    return fallback;
  }
  if (typeof value === 'number') {
    return value;
  }
  return String(value);
}

export function SocialSection({ isActive }) {
  const { user } = useAppState();

  const [friends, setFriends] = useState([]);
  const [friendsLoading, setFriendsLoading] = useState(false);
  const [friendsError, setFriendsError] = useState(null);
  const [friendStats, setFriendStats] = useState({});
  const [loadingFriendStats, setLoadingFriendStats] = useState({});

  const [groups, setGroups] = useState([]);
  const [groupsLoading, setGroupsLoading] = useState(false);
  const [groupsError, setGroupsError] = useState(null);
  const [showCreateGroup, setShowCreateGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState('');
  const [newGroupDescription, setNewGroupDescription] = useState('');
  const [invitations, setInvitations] = useState([]);
  const [invitationsLoading, setInvitationsLoading] = useState(false);
  const [invitationsError, setInvitationsError] = useState(null);
  const [groupMembers, setGroupMembers] = useState({});
  const [loadingMembers, setLoadingMembers] = useState({});

  const [searchTerm, setSearchTerm] = useState('');
  const [searchError, setSearchError] = useState(null);
  const [allUsers, setAllUsers] = useState([]);
  const [allUsersLoading, setAllUsersLoading] = useState(false);
  const [showUserDropdown, setShowUserDropdown] = useState(false);
  const [inviteGroupId, setInviteGroupId] = useState(null);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const searchInputRef = useRef(null);
  const dropdownRef = useRef(null);
  
  // Состояния для модалки поиска друзей
  const [showSearchFriendsModal, setShowSearchFriendsModal] = useState(false);
  const [searchFriendsTerm, setSearchFriendsTerm] = useState('');
  const [searchFriendsResults, setSearchFriendsResults] = useState([]);
  const [searchFriendsLoading, setSearchFriendsLoading] = useState(false);
  const [searchFriendsError, setSearchFriendsError] = useState(null);

  const [pendingCandidateId, setPendingCandidateId] = useState(null);
  const [pendingFriendshipId, setPendingFriendshipId] = useState(null);
  const [selectedUserForInvite, setSelectedUserForInvite] = useState(null);
  const [showGroupSelectForInvite, setShowGroupSelectForInvite] = useState(false);
  
  // Состояния для модальных окон подтверждения
  const [deleteGroupConfirm, setDeleteGroupConfirm] = useState({ isOpen: false, groupId: null });
  const [removeMemberConfirm, setRemoveMemberConfirm] = useState({ isOpen: false, groupId: null, memberUserId: null });

  const loadAllUsers = useCallback(async () => {
    setAllUsersLoading(true);
    try {
      const data = await getAllUsers();
      setAllUsers(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Ошибка загрузки пользователей:', error);
    } finally {
      setAllUsersLoading(false);
    }
  }, []);

  const loadFriends = useCallback(async () => {
    if (!user?.id) {
      setFriends([]);
      setFriendsError(null);
      return;
    }
    setFriendsLoading(true);
    setFriendsError(null);
    try {
      const data = await listFriends(user.id);
      setFriends(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Ошибка загрузки друзей:', error);
      setFriendsError(error.message ?? 'Не удалось загрузить друзей');
    } finally {
      setFriendsLoading(false);
    }
  }, [user?.id]);

  const loadFriendStats = useCallback(async (friendId) => {
    if (loadingFriendStats[friendId] || friendStats[friendId]) {
      return;
    }
    setLoadingFriendStats(prev => ({ ...prev, [friendId]: true }));
    try {
      const stats = await getFriendStatistics(friendId);
      setFriendStats(prev => ({ ...prev, [friendId]: stats }));
    } catch (error) {
      console.error(`Ошибка загрузки статистики друга ${friendId}:`, error);
    } finally {
      setLoadingFriendStats(prev => ({ ...prev, [friendId]: false }));
    }
  }, [loadingFriendStats, friendStats]);

  const loadGroups = useCallback(async () => {
    if (!user?.id) {
      setGroups([]);
      setGroupsError(null);
      return;
    }
    setGroupsLoading(true);
    setGroupsError(null);
    try {
      const data = await listGroups(user.id);
      setGroups(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Ошибка загрузки групп:', error);
      setGroupsError(error.message ?? 'Не удалось загрузить группы');
    } finally {
      setGroupsLoading(false);
    }
  }, [user?.id]);

  const loadInvitations = useCallback(async () => {
    if (!user?.id) {
      setInvitations([]);
      setInvitationsError(null);
      return;
    }
    setInvitationsLoading(true);
    setInvitationsError(null);
    try {
      console.log('Загрузка приглашений для пользователя:', user.id);
      const data = await getGroupInvitations(user.id);
      console.log('Получены приглашения:', data);
      const invitationsArray = Array.isArray(data) ? data : [];
      console.log('Обработанные приглашения:', invitationsArray);
      setInvitations(invitationsArray);
      if (invitationsArray.length === 0) {
        console.log('Приглашений не найдено для пользователя:', user.id);
      }
    } catch (error) {
      console.error('Ошибка загрузки приглашений:', error);
      console.error('Детали ошибки:', {
        message: error.message,
        stack: error.stack,
        response: error.response
      });
      setInvitationsError(error.message ?? 'Не удалось загрузить приглашения');
      setInvitations([]);
    } finally {
      setInvitationsLoading(false);
    }
  }, [user?.id]);

  const loadGroupMembers = useCallback(async (groupId) => {
    if (!user?.id || loadingMembers[groupId] || groupMembers[groupId]) {
      return;
    }
    setLoadingMembers(prev => ({ ...prev, [groupId]: true }));
    try {
      const data = await getGroupMembers(groupId, user.id);
      setGroupMembers(prev => ({ ...prev, [groupId]: Array.isArray(data) ? data : [] }));
    } catch (error) {
      console.error(`Ошибка загрузки участников группы ${groupId}:`, error);
    } finally {
      setLoadingMembers(prev => ({ ...prev, [groupId]: false }));
    }
  }, [user?.id, loadingMembers, groupMembers]);


  useEffect(() => {
    if (isActive) {
      loadAllUsers();
      loadGroups();
      loadInvitations();
      if (user?.id) {
        loadFriends();
      }
      
      // Автоматически обновляем приглашения каждые 10 секунд
      const invitationsInterval = setInterval(() => {
        if (user?.id) {
          loadInvitations();
        }
      }, 10000);
      
      return () => {
        clearInterval(invitationsInterval);
      };
    }
  }, [isActive, user?.id, loadGroups, loadInvitations]);

  // Закрытие выпадающего меню при клике вне его
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target) &&
          searchInputRef.current && !searchInputRef.current.contains(event.target)) {
        setShowUserDropdown(false);
      }
      // Обработка клика вне области для поиска пользователей
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSearchFocus = useCallback(() => {
    if (!user?.id) return;
    setShowUserDropdown(true);
  }, [user?.id]);

  const handleSearchChange = useCallback(
    (event) => {
      const term = event.target.value;
      setSearchTerm(term);
      setShowUserDropdown(true);
      // Сбрасываем выбранного пользователя при изменении поискового запроса
      if (term !== selectedUserForInvite?.username) {
        setSelectedUserForInvite(null);
      }
    },
    [selectedUserForInvite]
  );

  const handleUserSelect = useCallback((selectedUser) => {
    setSearchTerm(selectedUser.username);
    setSelectedUserForInvite(selectedUser);
    setShowUserDropdown(false);
    // После выбора пользователя можно выполнить поиск, если нужно
    // Но карточки не показываем, только выпадающее меню
  }, []);

  const handleInviteFromSearch = useCallback(async (groupId) => {
    if (!selectedUserForInvite || !user?.id) {
      return;
    }
    try {
      await inviteUserToGroup(groupId, selectedUserForInvite.id, user.id);
      await loadGroups();
      await loadInvitations();
      setSelectedUserForInvite(null);
      setSearchTerm('');
      setShowGroupSelectForInvite(false);
    } catch (error) {
      console.error('Ошибка приглашения в группу:', error);
      setGroupsError(error.message ?? 'Не удалось пригласить пользователя');
    }
  }, [selectedUserForInvite, user?.id, loadGroups, loadInvitations]);

  // Функция загрузки всех пользователей для модалки
  const loadAllUsersForModal = useCallback(
    async () => {
      if (!user?.id) {
        return;
      }
      setSearchFriendsLoading(true);
      setSearchFriendsError(null);
      try {
        const allUsersData = await getAllUsers();
        const usersList = Array.isArray(allUsersData) ? allUsersData : [];
        
        // Преобразуем в формат, похожий на FriendCandidateResponse
        const candidates = usersList
          .filter(u => u.id !== user.id)
          .map(u => {
            // Находим информацию о дружбе
            const existingFriendship = friends.find(f => {
              const otherUser = f.user?.id === user.id ? f.friend : f.user;
              return otherUser?.id === u.id;
            });
            
            return {
              id: u.id,
              username: u.username,
              email: u.email,
              friendship_id: existingFriendship?.id || null,
              friendship_status: existingFriendship?.status || null,
              is_incoming: existingFriendship?.status?.toLowerCase() === 'pending' && existingFriendship?.user_id !== user.id,
              is_outgoing: existingFriendship?.status?.toLowerCase() === 'pending' && existingFriendship?.user_id === user.id
            };
          });
        
        setSearchFriendsResults(candidates);
      } catch (error) {
        console.error('Ошибка загрузки пользователей:', error);
        setSearchFriendsError(error.message ?? 'Не удалось загрузить пользователей');
        setSearchFriendsResults([]);
      } finally {
        setSearchFriendsLoading(false);
      }
    },
    [user?.id, friends]
  );

  // Функция поиска друзей для модалки
  const performSearchFriends = useCallback(
    async (term) => {
      if (!user?.id) {
        return;
      }
      
      // Если запрос пустой или меньше 2 символов, показываем всех пользователей
      if (!term || term.trim().length < 2) {
        await loadAllUsersForModal();
        return;
      }
      
      setSearchFriendsLoading(true);
      setSearchFriendsError(null);
      try {
        const results = await searchFriendCandidates(term.trim(), user.id, { limit: 50 });
        setSearchFriendsResults(Array.isArray(results) ? results : []);
      } catch (error) {
        console.error('Ошибка поиска друзей:', error);
        setSearchFriendsError(error.message ?? 'Не удалось выполнить поиск');
        setSearchFriendsResults([]);
      } finally {
        setSearchFriendsLoading(false);
      }
    },
    [user?.id, loadAllUsersForModal]
  );

  // Обработчик изменения поискового запроса в модалке
  const handleSearchFriendsChange = useCallback(
    (event) => {
      const term = event.target.value;
      setSearchFriendsTerm(term);
      // Используем debounce для поиска, но для пустого запроса сразу показываем всех
      if (term.trim().length === 0) {
        loadAllUsersForModal();
      } else if (term.trim().length >= 2) {
        performSearchFriends(term.trim());
      } else {
        // При 1 символе показываем всех (можно оставить пустым или показать всех)
        loadAllUsersForModal();
      }
    },
    [performSearchFriends, loadAllUsersForModal]
  );

  const handleSendFriendRequest = useCallback(
    async (friendId) => {
      if (!user?.id) {
        return;
      }
      setPendingCandidateId(friendId);
      setSearchError(null);
      try {
        await sendFriendRequest(user.id, friendId);
        await loadFriends();
        setShowUserDropdown(false);
        setSearchTerm('');
        // Обновляем результаты поиска в модалке, если она открыта
        if (showSearchFriendsModal) {
          if (searchFriendsTerm.trim().length >= 2) {
            await performSearchFriends(searchFriendsTerm.trim());
          } else {
            await loadAllUsersForModal();
          }
        }
      } catch (error) {
        console.error('Ошибка отправки запроса в друзья:', error);
        setSearchError(error.message ?? 'Не удалось отправить запрос');
      } finally {
        setPendingCandidateId(null);
      }
    },
    [user?.id, loadFriends, showSearchFriendsModal, searchFriendsTerm, performSearchFriends, loadAllUsersForModal]
  );

  const handleAcceptFriendship = useCallback(
    async (friendshipId) => {
      setPendingFriendshipId(friendshipId);
      setFriendsError(null);
      try {
        await acceptFriendRequest(friendshipId);
        await loadFriends();
        // Обновляем результаты поиска в модалке, если она открыта
        if (showSearchFriendsModal) {
          if (searchFriendsTerm.trim().length >= 2) {
            await performSearchFriends(searchFriendsTerm.trim());
          } else {
            await loadAllUsersForModal();
          }
        }
      } catch (error) {
        console.error('Ошибка подтверждения дружбы:', error);
        setFriendsError(error.message ?? 'Не удалось подтвердить дружбу');
      } finally {
        setPendingFriendshipId(null);
      }
    },
    [loadFriends, showSearchFriendsModal, searchFriendsTerm, performSearchFriends, loadAllUsersForModal]
  );

  const handleRemoveFriendship = useCallback(
    async (friendshipId) => {
      setPendingFriendshipId(friendshipId);
      setFriendsError(null);
      setSearchError(null);
      try {
        await removeFriendship(friendshipId);
        await loadFriends();
      } catch (error) {
        console.error('Ошибка удаления дружбы:', error);
        const message = error.message ?? 'Не удалось обновить статус дружбы';
        setFriendsError(message);
        setSearchError(message);
      } finally {
        setPendingFriendshipId(null);
      }
    },
    [loadFriends]
  );

  const handleCreateGroup = useCallback(async () => {
    if (!newGroupName.trim() || !user?.id) {
      return;
    }
    try {
      await createGroup(newGroupName.trim(), newGroupDescription.trim() || null, user.id);
      setNewGroupName('');
      setNewGroupDescription('');
      setShowCreateGroup(false);
      await loadGroups();
    } catch (error) {
      console.error('Ошибка создания группы:', error);
      setGroupsError(error.message ?? 'Не удалось создать группу');
    }
  }, [newGroupName, newGroupDescription, user?.id, loadGroups]);

  const handleInviteToGroup = useCallback(async (groupId, userId) => {
    if (!user?.id) {
      return;
    }
    try {
      console.log('Отправка приглашения в группу:', { groupId, userId, inviterId: user.id });
      const result = await inviteUserToGroup(groupId, userId, user.id);
      console.log('Приглашение отправлено, результат:', result);
      // Обновляем списки групп и приглашений
      await loadGroups();
      // Небольшая задержка перед загрузкой приглашений, чтобы БД успела обновиться
      setTimeout(async () => {
        await loadInvitations();
      }, 500);
      setShowInviteModal(false);
      setInviteGroupId(null);
    } catch (error) {
      console.error('Ошибка приглашения в группу:', error);
      setGroupsError(error.message ?? 'Не удалось пригласить пользователя');
    }
  }, [loadGroups, loadInvitations, user?.id]);

  const handleAcceptInvitation = useCallback(async (invitationId) => {
    try {
      await acceptGroupInvitation(invitationId);
      await loadGroups();
      await loadInvitations();
    } catch (error) {
      console.error('Ошибка принятия приглашения:', error);
      setInvitationsError(error.message ?? 'Не удалось принять приглашение');
    }
  }, [loadGroups, loadInvitations]);

  const handleRejectInvitation = useCallback(async (invitationId) => {
    try {
      await rejectGroupInvitation(invitationId);
      await loadGroups();
      await loadInvitations();
    } catch (error) {
      console.error('Ошибка отклонения приглашения:', error);
      setInvitationsError(error.message ?? 'Не удалось отклонить приглашение');
    }
  }, [loadGroups, loadInvitations]);

  const handleDeleteGroup = useCallback((groupId) => {
    if (!user?.id) {
      return;
    }
    setDeleteGroupConfirm({ isOpen: true, groupId });
  }, [user?.id]);

  const handleDeleteGroupConfirm = useCallback(async () => {
    if (!user?.id || !deleteGroupConfirm.groupId) {
      return;
    }
    try {
      await deleteGroup(deleteGroupConfirm.groupId, user.id);
      await loadGroups();
      setDeleteGroupConfirm({ isOpen: false, groupId: null });
    } catch (error) {
      console.error('Ошибка удаления группы:', error);
      setGroupsError(error.message ?? 'Не удалось удалить группу');
      setDeleteGroupConfirm({ isOpen: false, groupId: null });
    }
  }, [deleteGroupConfirm.groupId, loadGroups, user?.id]);

  const handleRemoveMember = useCallback((groupId, memberUserId) => {
    if (!user?.id) {
      return;
    }
    setRemoveMemberConfirm({ isOpen: true, groupId, memberUserId });
  }, [user?.id]);

  const handleRemoveMemberConfirm = useCallback(async () => {
    if (!user?.id || !removeMemberConfirm.groupId || !removeMemberConfirm.memberUserId) {
      return;
    }
    try {
      await removeGroupMember(removeMemberConfirm.groupId, removeMemberConfirm.memberUserId, user.id);
      await loadGroups();
      // Обновить список участников
      setGroupMembers(prev => {
        const newMembers = { ...prev };
        if (newMembers[removeMemberConfirm.groupId]) {
          newMembers[removeMemberConfirm.groupId] = newMembers[removeMemberConfirm.groupId].filter(
            m => m.user_id !== removeMemberConfirm.memberUserId
          );
        }
        return newMembers;
      });
      setRemoveMemberConfirm({ isOpen: false, groupId: null, memberUserId: null });
    } catch (error) {
      console.error('Ошибка удаления участника:', error);
      setGroupsError(error.message ?? 'Не удалось удалить участника');
      setRemoveMemberConfirm({ isOpen: false, groupId: null, memberUserId: null });
    }
  }, [removeMemberConfirm.groupId, removeMemberConfirm.memberUserId, loadGroups, user?.id]);

  const handleInviteButtonClick = useCallback((groupId, event) => {
    event.stopPropagation();
    setInviteGroupId(groupId);
    setShowInviteModal(true);
  }, []);

  // Получаем список друзей для приглашения
  const acceptedFriends = useMemo(() => {
    return friends
      .filter(f => {
        const statusKey = String(f.status ?? '').toLowerCase();
        return statusKey === 'accepted';
      })
      .map(f => {
        const otherUser = f.user?.id === user?.id ? f.friend : f.user;
        return {
          id: otherUser?.id,
          username: otherUser?.username,
          email: otherUser?.email
        };
      })
      .filter(f => f.id && f.id !== user?.id);
  }, [friends, user?.id]);

  const renderFriendCard = useCallback(
    (friendship) => {
      const statusKey = String(friendship.status ?? '').toLowerCase();
      const status = FRIEND_STATUS[statusKey] ?? { label: 'Неизвестно', tone: 'neutral' };
      const otherUser =
        friendship.user?.id === user?.id ? friendship.friend : friendship.user;
      const otherUsername = otherUser?.username
        ? `@${otherUser.username}`
        : `Пользователь #${otherUser?.id ?? '—'}`;
      const isPendingIncoming = statusKey === 'pending' && friendship.user_id !== user?.id;
      const isPendingOutgoing = statusKey === 'pending' && friendship.user_id === user?.id;
      const isBlocked = statusKey === 'blocked';
      const isAccepted = statusKey === 'accepted';
      const actionDisabled = pendingFriendshipId === friendship.id;
      const friendId = otherUser?.id;
      const stats = friendStats[friendId];
      const loadingStats = loadingFriendStats[friendId];

      return (
        <div key={friendship.id} className="card friend-card social-card">
          <div className="card-header">
            <div className="card-title">{otherUsername}</div>
            <Badge tone={status.tone}>{status.label}</Badge>
          </div>
          <div className="social-muted">ID: {otherUser?.id ?? '—'}</div>
          {isAccepted && friendId ? (
            <div className="social-card__stats">
              <Button
                variant="ghost"
                size="sm"
                loading={loadingStats}
                icon={stats ? <RefreshCw size={16} aria-hidden="true" /> : <BarChart3 size={16} aria-hidden="true" />}
                onClick={() => loadFriendStats(friendId)}
              >
                {stats ? 'Обновить статистику' : 'Показать статистику'}
              </Button>
              {stats ? <FriendStats stats={stats} /> : null}
            </div>
          ) : null}
          <div className="social-card__actions">
            {isAccepted ? (
              <Button
                variant="ghost"
                size="sm"
                loading={actionDisabled}
                icon={<UserMinus size={16} aria-hidden="true" />}
                onClick={() => handleRemoveFriendship(friendship.id)}
              >
                Удалить из друзей
              </Button>
            ) : isPendingIncoming ? (
              <div className="social-card__row">
                <Button size="sm" loading={actionDisabled} icon={<Check size={16} aria-hidden="true" />} onClick={() => handleAcceptFriendship(friendship.id)}>
                  Принять
                </Button>
                <Button size="sm" variant="secondary" disabled={actionDisabled} icon={<X size={16} aria-hidden="true" />} onClick={() => handleRemoveFriendship(friendship.id)}>
                  Отклонить
                </Button>
              </div>
            ) : isPendingOutgoing ? (
              <Button size="sm" variant="secondary" loading={actionDisabled} onClick={() => handleRemoveFriendship(friendship.id)}>
                Отменить запрос
              </Button>
            ) : isBlocked ? (
              <span className="social-muted">Пользователь заблокирован</span>
            ) : null}
          </div>
        </div>
      );
    },
    [handleAcceptFriendship, handleRemoveFriendship, pendingFriendshipId, user?.id, friendStats, loadingFriendStats, loadFriendStats]
  );

  // Фильтрация пользователей для выпадающего меню
  const filteredUsersForDropdown = useMemo(() => {
    if (searchTerm.trim().length === 0) {
      // Если поле пустое, показываем всех пользователей
      return allUsers.filter(u => u.id !== user?.id);
    }
    // Фильтруем по поисковому запросу
    const searchLower = searchTerm.toLowerCase();
    return allUsers.filter(u => {
      if (u.id === user?.id) return false;
      return u.username?.toLowerCase().includes(searchLower) || 
             u.email?.toLowerCase().includes(searchLower);
    });
  }, [allUsers, user?.id, searchTerm]);

  return (
    <div className="social-screen">
      <div className="section-header">
        <h2 className="inline-icon">
          <Users size={22} aria-hidden="true" /> Социальное
        </h2>
      </div>

      <div className="social-block">
        <h3 className="section-subtitle">Поиск друзей</h3>
        <Button
          icon={<UserPlus size={16} aria-hidden="true" />}
          onClick={() => {
            setShowSearchFriendsModal(true);
            setSearchFriendsTerm('');
            setSearchFriendsResults([]);
            setSearchFriendsError(null);
            // Загружаем всех пользователей при открытии модалки
            if (user?.id) {
              loadAllUsersForModal();
            }
          }}
        >
          Найти друзей
        </Button>
      </div>

      <SectionBlock
        title="Друзья"
        isLoading={friendsLoading}
        error={friendsError}
        items={friends}
        emptyText="Друзей пока нет"
        renderItem={renderFriendCard}
        onRetry={loadFriends}
      />

      <div className="social-block">
        <div className="social-block__head">
          <h3 className="section-subtitle">Группы</h3>
          <Button
            size="sm"
            variant={showCreateGroup ? 'ghost' : 'secondary'}
            icon={showCreateGroup ? <X size={16} aria-hidden="true" /> : <Plus size={16} aria-hidden="true" />}
            onClick={() => setShowCreateGroup(!showCreateGroup)}
          >
            {showCreateGroup ? 'Отмена' : 'Создать группу'}
          </Button>
        </div>
        {showCreateGroup && (
          <div className="card social-card social-form">
            <div className="card-title">Новая группа</div>
            <input
              type="text"
              className="social-input"
              value={newGroupName}
              onChange={(e) => setNewGroupName(e.target.value)}
              placeholder="Название группы"
              aria-label="Название группы"
            />
            <textarea
              className="social-input social-input--area"
              value={newGroupDescription}
              onChange={(e) => setNewGroupDescription(e.target.value)}
              placeholder="Описание (необязательно)"
              aria-label="Описание группы"
            />
            <Button block onClick={handleCreateGroup} disabled={!newGroupName.trim()}>
              Создать
            </Button>
          </div>
        )}
        <SectionBlock
          title=""
          isLoading={groupsLoading}
          error={groupsError}
          items={groups}
          emptyText="Групп пока нет"
          onRetry={loadGroups}
          renderItem={(group) => {
            const isCreator = group.creator_id === user?.id;
            const isMember = group.members?.some(m => m.user_id === user?.id) || false;
            const members = groupMembers[group.id] || group.members || [];
            const showMembers = isCreator || isMember;

            return (
              <div key={group.id} className="card social-card">
                <div className="card-header">
                  <div className="card-title">{group.name}</div>
                  {isCreator ? <Badge tone="info">Вы создатель</Badge> : null}
                </div>
                {group.description ? <div className="card-description">{group.description}</div> : null}
                {showMembers && (
                  <div className="social-members">
                    <div className="social-members__head">
                      <strong>Участники ({members.length})</strong>
                      {!groupMembers[group.id] && !loadingMembers[group.id] && (
                        <Button size="sm" variant="ghost" onClick={() => loadGroupMembers(group.id)}>
                          Показать
                        </Button>
                      )}
                    </div>
                    {loadingMembers[group.id] ? (
                      <Spinner size="sm" label="Загружаем участников…" />
                    ) : groupMembers[group.id] ? (
                      <ul className="social-members__list">
                        {groupMembers[group.id].map(member => {
                          const displayName = member.user?.username
                            ? `@${member.user.username}`
                            : `Пользователь #${member.user_id}`;
                          const isMemberCreator = member.user_id === group.creator_id;

                          return (
                            <li key={member.id} className="social-member">
                              <span className="social-member__name">
                                {displayName}
                                {isMemberCreator ? <span className="social-member__role">создатель</span> : null}
                              </span>
                              {isCreator && !isMemberCreator && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  aria-label={`Удалить ${displayName} из группы`}
                                  icon={<UserMinus size={16} aria-hidden="true" />}
                                  onClick={() => handleRemoveMember(group.id, member.user_id)}
                                >
                                  Удалить
                                </Button>
                              )}
                            </li>
                          );
                        })}
                      </ul>
                    ) : null}
                  </div>
                )}
                {!showMembers ? <div className="social-muted">Участников: {group.members?.length ?? 0}</div> : null}
                {isCreator && (
                  <div className="social-card__actions">
                    <Button size="sm" block icon={<UserPlus size={16} aria-hidden="true" />} onClick={(e) => handleInviteButtonClick(group.id, e)}>
                      Пригласить
                    </Button>
                    <Button size="sm" variant="ghost" block icon={<Trash2 size={16} aria-hidden="true" />} onClick={() => handleDeleteGroup(group.id)}>
                      Удалить группу
                    </Button>
                  </div>
                )}
              </div>
            );
          }}
        />
      </div>

      <SectionBlock
        title="Приглашения в группы"
        isLoading={invitationsLoading}
        error={invitationsError}
        items={invitations}
        emptyText="Приглашений нет"
        onRetry={loadInvitations}
        renderItem={(invitation) => (
          <div key={invitation.id} className="card social-card">
            <div className="card-header">
              <div className="card-title">
                {invitation.group?.name || `Группа #${invitation.group_id}`}
              </div>
              <Badge tone="warning">{INVITATION_STATUS[String(invitation.status || 'pending').toLowerCase()] ?? 'Ожидает ответа'}</Badge>
            </div>
            {invitation.group?.description && (
              <div className="card-description">{invitation.group.description}</div>
            )}
            <div className="social-card__row">
              <Button size="sm" icon={<Check size={16} aria-hidden="true" />} onClick={() => handleAcceptInvitation(invitation.id)}>
                Принять
              </Button>
              <Button size="sm" variant="secondary" icon={<X size={16} aria-hidden="true" />} onClick={() => handleRejectInvitation(invitation.id)}>
                Отклонить
              </Button>
            </div>
          </div>
        )}
      />

      {/* Модальные окна подтверждения */}
      <ConfirmModal
        isOpen={deleteGroupConfirm.isOpen}
        onClose={() => setDeleteGroupConfirm({ isOpen: false, groupId: null })}
        onConfirm={handleDeleteGroupConfirm}
        title="Удаление группы"
        message="Вы уверены, что хотите удалить эту группу? Это действие нельзя отменить."
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />

      <ConfirmModal
        isOpen={removeMemberConfirm.isOpen}
        onClose={() => setRemoveMemberConfirm({ isOpen: false, groupId: null, memberUserId: null })}
        onConfirm={handleRemoveMemberConfirm}
        title="Удаление участника"
        message="Вы уверены, что хотите удалить этого участника из группы?"
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />

      {/* Модальное окно для выбора друга для приглашения в группу */}
      <Modal
        isOpen={showInviteModal && inviteGroupId !== null}
        onClose={() => {
          setShowInviteModal(false);
          setInviteGroupId(null);
        }}
        title="Пригласить друга в группу"
      >
        {acceptedFriends.length === 0 ? (
          <StateView state="empty" title="Некого пригласить" message="Сначала добавьте друзей — пригласить можно только их." compact />
        ) : (
          <div className="social-picker">
            {acceptedFriends.map(friend => (
              <button
                key={friend.id}
                type="button"
                onClick={() => {
                  if (inviteGroupId) {
                    handleInviteToGroup(inviteGroupId, friend.id);
                  }
                }}
                className="user-dropdown-item social-picker__item"
              >
                <span className="user-dropdown-item-name">@{friend.username || `Пользователь #${friend.id}`}</span>
                {friend.email && (
                  <span className="user-dropdown-item-email">{friend.email}</span>
                )}
              </button>
            ))}
          </div>
        )}
      </Modal>

      {/* Модальное окно для поиска друзей */}
      <Modal
        isOpen={showSearchFriendsModal}
        onClose={() => {
          setShowSearchFriendsModal(false);
          setSearchFriendsTerm('');
          setSearchFriendsResults([]);
          setSearchFriendsError(null);
        }}
        title="Поиск друзей"
      >
        <div className="social-search">
          <div className="social-search__field">
            <Search size={16} className="social-search__icon" aria-hidden="true" />
            <input
              type="text"
              value={searchFriendsTerm}
              onChange={handleSearchFriendsChange}
              placeholder="Логин или email"
              aria-label="Поиск по логину или email"
              className="search-input social-input social-input--search"
            />
          </div>

          {searchFriendsError && (
            <div className="inline-error" role="alert">
              {searchFriendsError}
            </div>
          )}

          {searchFriendsLoading && <StateView state="loading" compact />}

          {!searchFriendsLoading && !searchFriendsError && searchFriendsResults.length === 0 && (
            <StateView state="empty" title="Пользователи не найдены" compact />
          )}

          {!searchFriendsLoading && !searchFriendsError && searchFriendsResults.length > 0 && (
            <div className="social-picker">
              {searchFriendsResults.map(candidate => {
                const friendshipStatus = candidate.friendship_status?.toLowerCase();
                const isFriend = friendshipStatus === 'accepted';
                const isPendingIncoming = candidate.is_incoming === true;
                const isPendingOutgoing = candidate.is_outgoing === true;

                return (
                  <div key={candidate.id} className="social-candidate">
                    <div className="social-candidate__info">
                      <div className="user-dropdown-item-name">
                        @{candidate.username || `Пользователь #${candidate.id}`}
                      </div>
                      {candidate.email && (
                        <div className="user-dropdown-item-email">{candidate.email}</div>
                      )}
                    </div>
                    <div className="social-candidate__action">
                      {isFriend ? (
                        <Badge tone="success">В друзьях</Badge>
                      ) : isPendingIncoming ? (
                        <Button
                          size="sm"
                          loading={pendingFriendshipId === candidate.friendship_id}
                          onClick={() => {
                            if (candidate.friendship_id) {
                              handleAcceptFriendship(candidate.friendship_id);
                            }
                          }}
                        >
                          Принять
                        </Button>
                      ) : isPendingOutgoing ? (
                        <Badge tone="warning">Запрос отправлен</Badge>
                      ) : (
                        <Button
                          size="sm"
                          variant="secondary"
                          loading={pendingCandidateId === candidate.id}
                          icon={<UserPlus size={16} aria-hidden="true" />}
                          onClick={() => handleSendFriendRequest(candidate.id)}
                        >
                          Добавить
                        </Button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </Modal>
    </div>
  );
}
