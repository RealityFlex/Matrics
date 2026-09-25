import { apiCall, apiDelete, apiPost, apiPut } from './apiClient.js';

export function getUserTasks(userId) {
  return apiCall(`/tasks/user/${userId}`);
}

export function createTask(userId, payload) {
  return apiPost(`/tasks/?user_id=${userId}`, payload);
}

export function updateTask(taskId, payload) {
  return apiPut(`/tasks/${taskId}`, payload);
}

export function deleteTask(taskId) {
  return apiDelete(`/tasks/${taskId}`);
}

export function completeTask(taskId) {
  return apiPost(`/tasks/${taskId}/complete`);
}

export function getTask(taskId) {
  return apiCall(`/tasks/${taskId}`);
}

export function getGenerateStatus(userId) {
  return apiCall(`/tasks/generate/status?user_id=${userId}`);
}

export function generateTask(userId) {
  return apiPost(`/tasks/generate?user_id=${userId}`);
}

// ===== Цели =====
export function getUserGoals(userId) {
  return apiCall(`/tasks/goals/users/${userId}`);
}

export function createGoal(userId, payload) {
  return apiPost(`/tasks/goals/?user_id=${userId}`, payload);
}

export function updateGoal(goalId, payload) {
  return apiPut(`/tasks/goals/${goalId}`, payload);
}

export function deleteGoal(goalId) {
  return apiDelete(`/tasks/goals/${goalId}`);
}

export function updateGoalTask(goalId, taskId, payload) {
  return apiPut(`/tasks/goals/${goalId}/tasks/${taskId}`, payload);
}

export function completeGoal(goalId) {
  return apiPost(`/tasks/goals/${goalId}/complete`);
}

