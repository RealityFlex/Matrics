import { apiCall, apiPost } from './apiClient.js';

export function getAllUsers() {
  return apiCall('/users/');
}

export function listFriends(userId) {
  if (!userId) {
    return Promise.resolve([]);
  }
  return apiCall(`/social/friendships/users/${userId}`);
}

export function listGroups(userId) {
  if (!userId) {
    return Promise.resolve([]);
  }
  const params = new URLSearchParams({
    user_id: String(userId)
  });
  return apiCall(`/social/groups/?${params.toString()}`);
}

export function searchFriendCandidates(query, userId, { limit = 10 } = {}) {
  if (!userId || !query || !query.trim()) {
    return Promise.resolve([]);
  }
  const params = new URLSearchParams({
    query: query.trim(),
    user_id: String(userId),
    limit: String(limit)
  });
  return apiCall(`/social/friendships/search?${params.toString()}`);
}

export function sendFriendRequest(userId, friendId) {
  const params = new URLSearchParams({
    user_id: String(userId),
    friend_id: String(friendId)
  });
  return apiCall(`/social/friendships/request?${params.toString()}`, {
    method: 'POST'
  });
}

export function acceptFriendRequest(friendshipId) {
  return apiCall(`/social/friendships/${friendshipId}/accept`, {
    method: 'POST'
  });
}

export function removeFriendship(friendshipId) {
  return apiCall(`/social/friendships/${friendshipId}`, {
    method: 'DELETE'
  });
}

export function createGroup(name, description, creatorId) {
  if (!creatorId) {
    return Promise.reject(new Error('ID создателя обязателен'));
  }
  const params = new URLSearchParams({
    creator_id: String(creatorId)
  });
  return apiPost(`/social/groups/?${params.toString()}`, { name, description });
}

export function inviteUserToGroup(groupId, userId, inviterUserId) {
  if (!inviterUserId) {
    return Promise.reject(new Error('ID приглашающего обязателен'));
  }
  const params = new URLSearchParams({
    user_id: String(userId),
    inviter_user_id: String(inviterUserId)
  });
  return apiCall(`/social/groups/${groupId}/members/add?${params.toString()}`, {
    method: 'POST'
  });
}

export function getGroupInvitations(userId) {
  if (!userId) {
    return Promise.resolve([]);
  }
  return apiCall(`/social/groups/invitations/user/${userId}`);
}

export function acceptGroupInvitation(invitationId) {
  return apiCall(`/social/groups/invitations/${invitationId}/accept`, {
    method: 'POST'
  });
}

export function rejectGroupInvitation(invitationId) {
  return apiCall(`/social/groups/invitations/${invitationId}/reject`, {
    method: 'POST'
  });
}

export function deleteGroup(groupId, requesterId) {
  if (!requesterId) {
    return Promise.reject(new Error('ID запрашивающего обязателен'));
  }
  const params = new URLSearchParams({
    requester_id: String(requesterId)
  });
  return apiCall(`/social/groups/${groupId}?${params.toString()}`, {
    method: 'DELETE'
  });
}

export function removeGroupMember(groupId, userId, requesterId) {
  if (!requesterId) {
    return Promise.reject(new Error('ID запрашивающего обязателен'));
  }
  const params = new URLSearchParams({
    requester_id: String(requesterId)
  });
  return apiCall(`/social/groups/${groupId}/members/${userId}?${params.toString()}`, {
    method: 'DELETE'
  });
}

export function getGroupMembers(groupId, userId) {
  if (!userId) {
    return Promise.reject(new Error('ID пользователя обязателен'));
  }
  const params = new URLSearchParams({
    user_id: String(userId)
  });
  return apiCall(`/social/groups/${groupId}/members?${params.toString()}`);
}

export function getFriendStatistics(friendId) {
  return apiCall(`/statistics/stats/users/${friendId}/summary`);
}

