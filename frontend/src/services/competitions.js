import { apiCall } from './apiClient.js';

export function listCompetitions({ activeOnly = false, userId = null } = {}) {
  const params = new URLSearchParams();
  if (activeOnly) {
    params.set('active_only', 'true');
  }
  if (userId) {
    params.set('user_id', userId.toString());
  }
  const query = params.toString();
  return apiCall(`/competitions/competitions/${query ? `?${query}` : ''}`);
}

export function joinCompetition(competitionId, userId) {
  return apiCall(`/competitions/competitions/${competitionId}/join?user_id=${userId}`, {
    method: 'POST'
  });
}

export function declineCompetition(competitionId, userId) {
  return apiCall(`/competitions/competitions/${competitionId}/decline?user_id=${userId}`, {
    method: 'POST'
  });
}

export function getUserCompetitionParticipation(competitionId, userId) {
  if (!userId) {
    return Promise.resolve(null);
  }
  return apiCall(`/competitions/competitions/${competitionId}/participants/${userId}`)
    .catch((error) => {
      // Если 404 - пользователь не участвует, это нормально
      if (error?.status === 404 || error?.message?.includes('404')) {
        return null;
      }
      // Для других ошибок логируем и возвращаем null
      console.error('Ошибка проверки участия:', error);
      return null;
    });
}

export function getUserCompetitionProgress(competitionId, userId) {
  if (!userId) {
    return Promise.resolve(null);
  }
  return apiCall(`/competitions/competitions/${competitionId}/progress/${userId}`).catch(() => null);
}

export function listUserChallenges(userId) {
  if (!userId) {
    return Promise.resolve([]);
  }
  return apiCall(`/competitions/challenges/users/${userId}`);
}

export function createChallenge(payload) {
  return apiCall('/competitions/challenges/', {
    method: 'POST',
    body: JSON.stringify(payload)
  });
}

export function acceptChallenge(challengeId, userId) {
  return apiCall(`/competitions/challenges/${challengeId}/accept`, {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId
    })
  });
}

export function declineChallenge(challengeId, userId) {
  return apiCall(`/competitions/challenges/${challengeId}/decline`, {
    method: 'POST',
    body: JSON.stringify({
      user_id: userId
    })
  });
}

export function getCompetitionLeaderboard(competitionId) {
  return apiCall(`/competitions/competitions/${competitionId}/leaderboard`);
}

