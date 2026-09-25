import { apiCall, apiDelete, apiPost, apiPut, authHeaders, getApiBase } from '../services/apiClient.js';

export const adminApi = {
  // Items
  listItems() {
    return apiCall('/inventory/items/');
  },
  getItem(id) {
    return apiCall(`/inventory/items/${id}`);
  },
  createItem(payload) {
    return apiPost('/inventory/items/', payload);
  },
  updateItem(id, payload) {
    return apiPut(`/inventory/items/${id}`, payload);
  },
  deleteItem(id) {
    return apiDelete(`/inventory/items/${id}`);
  },

  // Events
  listEvents() {
    return apiCall('/events/events/?upcoming_only=false');
  },
  getEvent(id) {
    return apiCall(`/events/events/${id}`);
  },
  createEvent(payload) {
    return apiPost('/events/events/', payload);
  },
  updateEvent(id, payload) {
    return apiPut(`/events/events/${id}`, payload);
  },
  deleteEvent(id) {
    return apiDelete(`/events/events/${id}`);
  },
  getEventCode(id) {
    return apiCall(`/events/events/${id}/code`);
  },
  getEventAttendances(id) {
    return apiCall(`/events/events/${id}/attendances`);
  },

  // Lessons
  listLessons() {
    return apiCall('/events/lessons/');
  },
  getLesson(id) {
    return apiCall(`/events/lessons/${id}`);
  },
  createLesson(payload) {
    return apiPost('/events/lessons/', payload);
  },
  updateLesson(id, payload) {
    return apiPut(`/events/lessons/${id}`, payload);
  },
  deleteLesson(id) {
    return apiDelete(`/events/lessons/${id}`);
  },
  getLessonCode(id) {
    return apiCall(`/events/lessons/${id}/qr`);
  },
  getLessonAttendances(id) {
    return apiCall(`/events/lessons/${id}/attendance`);
  },
  /** PNG с QR-диплинком на мини-приложение MAX (текущий код занятия) */
  async getLessonQrImageUrl(id) {
    const response = await fetch(`${getApiBase()}/events/lessons/${id}/qr-image`, { headers: authHeaders() });
    if (!response.ok) {
      throw new Error(`QR не загружен (HTTP ${response.status})`);
    }
    return URL.createObjectURL(await response.blob());
  },
  markLessonAttendanceManual(lessonId, userId) {
    return apiPost(`/events/lessons/${lessonId}/attendance/manual`, { user_id: userId });
  },
  importSchedule(payload) {
    return apiPost('/events/lessons/import', payload);
  },
  deleteImportBatch(batchId) {
    return apiDelete(`/events/lessons/import/${batchId}`);
  },
  seedDemoLessons(groupId, createdBy) {
    return apiPost('/events/lessons/demo-seed', { group_id: groupId, created_by: createdBy });
  },

  // Администрирование и роли
  verifyAdminToken() {
    return apiCall('/users/admin/verify');
  },
  setUserRole(userId, role, groupIds) {
    return apiPut(`/users/${userId}/role`, { role, group_ids: groupIds });
  },

  // Подключение организаций
  onboardOrganization(payload) {
    return apiPost('/users/organizations/onboard', payload);
  },
  listOrganizations() {
    return apiCall('/users/organizations');
  },
  async linkQrImageUrl(link) {
    const response = await fetch(`${getApiBase()}/users/qr?data=${encodeURIComponent(link)}`, { headers: authHeaders() });
    if (!response.ok) {
      throw new Error(`QR не загружен (HTTP ${response.status})`);
    }
    return URL.createObjectURL(await response.blob());
  },
  sendCuratorDigest() {
    return apiPost('/statistics/stats/curator/digest/send');
  },

  // Дашборд куратора (read-only)
  curatorGroups() {
    return apiCall('/statistics/stats/curator/groups');
  },
  curatorAttendance(groupId, days = 30) {
    const from = new Date(Date.now() - days * 86400000).toISOString();
    return apiCall(`/statistics/stats/curator/groups/${groupId}/attendance?date_from=${encodeURIComponent(from)}`);
  },
  curatorAtRisk(groupId, days = 7) {
    return apiCall(`/statistics/stats/curator/groups/${groupId}/at-risk?days=${days}`);
  },
  curatorWeekly(groupId, weeks = 8) {
    return apiCall(`/statistics/stats/curator/groups/${groupId}/weekly?weeks=${weeks}`);
  },

  listGroups() {
    return apiCall('/social/groups/');
  },
  getGroupMembers(groupId, userId) {
    return apiCall(`/social/groups/${groupId}/members?user_id=${userId}`);
  },

  // Achievements
  listAchievements() {
    return apiCall('/achievements/?include_hidden=true');
  },
  getAchievement(id) {
    return apiCall(`/achievements/${id}`);
  },
  createAchievement(payload) {
    return apiPost('/achievements/', payload);
  },
  updateAchievement(id, payload) {
    return apiPut(`/achievements/${id}`, payload);
  },
  deleteAchievement(id) {
    return apiDelete(`/achievements/${id}`);
  },

  // Shop
  listShopListings() {
    return apiCall('/economy/shop/listings/?active_only=false');
  },
  getShopListing(id) {
    return apiCall(`/economy/shop/listings/${id}`);
  },
  createShopListing(payload) {
    return apiPost('/economy/shop/listings/', payload);
  },
  updateShopListing(id, payload) {
    return apiPut(`/economy/shop/listings/${id}`, payload);
  },
  deleteShopListing(id) {
    return apiDelete(`/economy/shop/listings/${id}`);
  },

  // Users & stats
  listUsers() {
    return apiCall('/users/');
  },
  getUser(userId) {
    return apiCall(`/users/${userId}`);
  },
  getUserCharacter(userId) {
    return apiCall(`/characters/user/${userId}`);
  },
  getUserHabitStats(userId) {
    return apiCall(`/habits/stats/${userId}`);
  },
  getUserTaskStats(userId) {
    return apiCall(`/tasks/stats/${userId}`);
  },
  getUserEventStats(userId) {
    return apiCall(`/events/stats/${userId}`);
  },
  getUserAchievementStats(userId) {
    return apiCall(`/achievements/stats/${userId}`);
  },
  getUserCompetitionStats(userId) {
    return apiCall(`/competitions/stats/${userId}`);
  },
  getUserInventory(userId) {
    return apiCall(`/inventory/users/${userId}`);
  },
  getUserAchievements(userId) {
    return apiCall(`/achievements/users/${userId}`);
  },
  getUserTasks(userId) {
    return apiCall(`/tasks/user/${userId}`);
  },
  getUserHabits(userId) {
    return apiCall(`/habits/user/${userId}`);
  },
  getUserGoals(userId) {
    return apiCall(`/tasks/goals/users/${userId}`);
  },

  async loadStats() {
    try {
      const [users, items, events, achievements, shop, competitions, tasks, habits] = await Promise.allSettled([
        adminApi.listUsers(),
        adminApi.listItems(),
        adminApi.listEvents(),
        adminApi.listAchievements(),
        adminApi.listShopListings(),
        adminApi.listCompetitions(),
        apiCall('/tasks/').catch(() => []),
        apiCall('/habits/').catch(() => [])
      ]);
      
      // Получить глобальную статистику
      let globalStats = {};
      try {
        const statsData = await apiCall('/statistics/stats/global/overview');
        // Убеждаемся, что это объект, а не ошибка
        if (statsData && typeof statsData === 'object' && !statsData.error) {
          globalStats = statsData;
        }
      } catch (e) {
        console.warn('Не удалось загрузить глобальную статистику:', e);
      }
      
      // Убеждаемся, что все значения - числа
      const safeNumber = (value) => {
        if (typeof value === 'number' && !isNaN(value)) return value;
        if (typeof value === 'string') {
          const parsed = parseInt(value, 10);
          return isNaN(parsed) ? 0 : parsed;
        }
        return 0;
      };
      
      return {
        users: safeNumber(users.status === 'fulfilled' ? (Array.isArray(users.value) ? users.value.length : 0) : 0),
        items: safeNumber(items.status === 'fulfilled' ? (Array.isArray(items.value) ? items.value.length : 0) : 0),
        events: safeNumber(events.status === 'fulfilled' ? (Array.isArray(events.value) ? events.value.length : 0) : 0),
        achievements: safeNumber(achievements.status === 'fulfilled' ? (Array.isArray(achievements.value) ? achievements.value.length : 0) : 0),
        shop: safeNumber(shop.status === 'fulfilled' ? (Array.isArray(shop.value) ? shop.value.length : 0) : 0),
        competitions: safeNumber(competitions.status === 'fulfilled' ? (Array.isArray(competitions.value) ? competitions.value.length : 0) : 0),
        tasks: safeNumber(tasks.status === 'fulfilled' ? (Array.isArray(tasks.value) ? tasks.value.length : 0) : 0),
        habits: safeNumber(habits.status === 'fulfilled' ? (Array.isArray(habits.value) ? habits.value.length : 0) : 0),
        total_users: safeNumber(globalStats.total_users),
        total_tasks: safeNumber(globalStats.total_tasks),
        total_habits: safeNumber(globalStats.total_habits),
        total_competitions: safeNumber(globalStats.total_competitions),
        total_clans: safeNumber(globalStats.total_clans)
      };
    } catch (error) {
      console.error('Ошибка загрузки статистики:', error);
      return {
        users: 0,
        items: 0,
        events: 0,
        achievements: 0,
        shop: 0,
        competitions: 0,
        tasks: 0,
        habits: 0
      };
    }
  },

  // MAX Bot Settings
  getMaxBotSettings() {
    return apiCall('/bot/settings');
  },
  updateMaxBotSettings(payload) {
    return apiPut('/bot/settings', payload);
  },

  // Database reset
  resetDatabase() {
    return apiPost('/users/admin/reset-database');
  },

  // Competitions
  listCompetitions() {
    return apiCall('/competitions/competitions/?active_only=false');
  },
  getCompetition(id) {
    return apiCall(`/competitions/competitions/${id}`);
  },
  createCompetition(payload) {
    return apiPost('/competitions/competitions/', payload);
  },
  updateCompetition(id, payload) {
    return apiPut(`/competitions/competitions/${id}`, payload);
  },
  deleteCompetition(id) {
    return apiDelete(`/competitions/competitions/${id}`);
  },
  getCompetitionLeaderboard(id) {
    return apiCall(`/competitions/competitions/${id}/leaderboard`);
  },
  finalizeCompetition(id) {
    return apiPost(`/competitions/competitions/${id}/finalize`);
  }
};

export const ITEM_RARITY_OPTIONS = [
  { value: 'common', label: 'Обычный' },
  { value: 'uncommon', label: 'Необычный' },
  { value: 'rare', label: 'Редкий' },
  { value: 'epic', label: 'Эпический' },
  { value: 'legendary', label: 'Легендарный' }
];

// Значения совпадают с ItemType на бэкенде (services/shared/models/item.py)
export const ITEM_TYPE_OPTIONS = [
  { value: 'consumable', label: 'Расходуемый' },
  { value: 'equipment', label: 'Экипировка' },
  { value: 'decoration', label: 'Декорация' },
  { value: 'special', label: 'Особый' }
];

export const ACHIEVEMENT_REQUIREMENT_TYPES = [
  { value: 'tasks_completed', label: 'Задач выполнено' },
  { value: 'habits_logged', label: 'Привычки повторены' },
  { value: 'events_attended', label: 'Событий посещено' },
  { value: 'coins_earned', label: 'Монет заработано' },
  { value: 'intelligence_points_earned', label: 'Очков интеллекта заработано' },
  { value: 'lessons_attended', label: 'Посещено занятий' },
  { value: 'attendance_streak', label: 'Серия посещений подряд' }
];


