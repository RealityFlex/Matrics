import React, { useEffect, useMemo, useState } from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { listFriends } from '../../../services/social.js';
import { getUser } from '../../../services/users.js';
import { createChallenge } from '../../../services/competitions.js';
import { Button, StateView } from '../../../components/ui/index.jsx';

const METRIC_OPTIONS = [
  { value: 'tasks_completed', label: 'Выполненные задачи' },
  { value: 'habits_completed', label: 'Отмеченные привычки' },
  { value: 'coins_balance', label: 'Баланс монет' },
  { value: 'intelligence_points', label: 'Очки интеллекта' }
];

function formatFriend(friendship, currentUserId) {
  const otherUserId = friendship.friend_id === currentUserId ? friendship.user_id : friendship.friend_id;
  return {
    id: friendship.id,
    friendUserId: otherUserId,
    status: friendship.status
  };
}

export function ChallengeCreateModal({ isOpen, onClose, currentUser, onCreated }) {
  const [friendOptions, setFriendOptions] = useState([]);
  const [loadingFriends, setLoadingFriends] = useState(false);
  const [form, setForm] = useState({
    friendUserId: '',
    metricType: METRIC_OPTIONS[0].value,
    targetValue: '10',
    deadline: ''
  });
  const [errors, setErrors] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');

  const defaultDeadline = useMemo(() => {
    const oneDayLater = new Date(Date.now() + 24 * 60 * 60 * 1000);
    return oneDayLater.toISOString().slice(0, 16);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      setStatusMessage('');
      setErrors(null);
      return;
    }
    if (!form.deadline) {
      setForm((prev) => ({ ...prev, deadline: defaultDeadline }));
    }
    async function loadFriends() {
      if (!currentUser?.id) {
        return;
      }
      setLoadingFriends(true);
      setErrors(null);
      try {
        const list = await listFriends(currentUser.id);
        const accepted = (Array.isArray(list) ? list : [])
          .filter((item) => item.status === 'accepted')
          .map((item) => formatFriend(item, currentUser.id));

        const resolved = await Promise.all(
          accepted.map(async (item) => {
            try {
              const user = await getUser(item.friendUserId);
              return {
                optionId: item.id,
                userId: item.friendUserId,
                label: user?.username ? `${user.username} (#${item.friendUserId})` : `Пользователь #${item.friendUserId}`
              };
            } catch {
              return {
                optionId: item.id,
                userId: item.friendUserId,
                label: `Пользователь #${item.friendUserId}`
              };
            }
          })
        );
        setFriendOptions(resolved);
        if (resolved.length > 0) {
          setForm((prev) => ({
            ...prev,
            friendUserId: prev.friendUserId || resolved[0].userId
          }));
        }
      } catch (error) {
        setErrors(error.message ?? 'Не удалось загрузить список друзей');
      } finally {
        setLoadingFriends(false);
      }
    }
    loadFriends();
  }, [isOpen, currentUser?.id]);

  useEffect(() => {
    if (!isOpen) {
        setForm({
          friendUserId: '',
          metricType: METRIC_OPTIONS[0].value,
          targetValue: '10',
          deadline: defaultDeadline
        });
    }
  }, [isOpen, defaultDeadline]);

  const canSubmit = useMemo(() => {
    const targetValue = Number(form.targetValue) || 0;
    return Boolean(form.friendUserId) && targetValue > 0 && Boolean(form.deadline);
  }, [form.friendUserId, form.targetValue, form.deadline]);

  const handleChange = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canSubmit || !currentUser?.id) {
      return;
    }
    setIsSubmitting(true);
    setErrors(null);
    setStatusMessage('');
    try {
      const deadlineIso = new Date(form.deadline).toISOString();
      const payload = {
        challenger_id: currentUser.id,
        opponent_id: Number(form.friendUserId),
        metric_type: form.metricType,
        target_value: Number(form.targetValue) || 10,
        deadline: deadlineIso
      };
      const challenge = await createChallenge(payload);
      setStatusMessage('Челлендж создан!');
      if (onCreated) {
        onCreated(challenge);
      }
      onClose();
    } catch (error) {
      setErrors(error.message ?? 'Не удалось создать челлендж');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Создать челлендж">
      {loadingFriends ? (
        <StateView state="loading" message="Загружаем друзей…" compact />
      ) : friendOptions.length === 0 ? (
        <StateView
          state={errors ? 'error' : 'empty'}
          title={errors ? 'Не удалось загрузить друзей' : 'Пока некого вызвать'}
          message={errors || 'Челлендж можно отправить только другу, который принял заявку в друзья.'}
          compact
        />
      ) : (
        <form onSubmit={handleSubmit} className="form-group comp-form">
          <div>
            <label htmlFor="challengeFriend">Выберите друга</label>
            <select
              id="challengeFriend"
              value={form.friendUserId}
              onChange={(event) => handleChange('friendUserId', event.target.value)}
            >
              {friendOptions.map((option) => (
                <option key={option.optionId} value={option.userId}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="challengeMetric">Показатель</label>
            <select
              id="challengeMetric"
              value={form.metricType}
              onChange={(event) => handleChange('metricType', event.target.value)}
            >
              {METRIC_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="challengeTarget">Цель</label>
            <input
              type="number"
              id="challengeTarget"
              min="1"
              value={form.targetValue === 0 || form.targetValue === '0' ? '' : form.targetValue}
              onChange={(event) => handleChange('targetValue', event.target.value)}
            />
          </div>

          <div>
            <label htmlFor="challengeDeadline">Дедлайн</label>
            <input
              type="datetime-local"
              id="challengeDeadline"
              value={form.deadline}
              onChange={(event) => handleChange('deadline', event.target.value)}
            />
          </div>

          {errors ? (
            <div className="inline-error" role="alert">
              {errors}
            </div>
          ) : null}
          {statusMessage ? (
            <div className="comp-form__status" role="status">
              {statusMessage}
            </div>
          ) : null}

          <Button type="submit" block loading={isSubmitting} disabled={!canSubmit}>
            Создать
          </Button>
        </form>
      )}
    </Modal>
  );
}

