import { apiCall, apiPost } from './apiClient.js';

/** Мини-игра «Забег до пары» (competition-service /games/runner) */
const BASE = '/competitions/games/runner';

export function getGameOverview(userId) {
  return apiCall(`${BASE}/overview?user_id=${userId}`);
}

export function getGameLeaderboard(userId, scope = 'group') {
  return apiCall(`${BASE}/leaderboard?scope=${scope}&user_id=${userId}`);
}

export function startGameRun(userId) {
  return apiPost(`${BASE}/start?user_id=${userId}`);
}

export function finishGameRun(userId, runId, { distance, coins, durationMs }) {
  return apiPost(`${BASE}/runs/${runId}/finish?user_id=${userId}`, {
    distance: Math.floor(distance),
    coins,
    duration_ms: Math.floor(durationMs)
  });
}
