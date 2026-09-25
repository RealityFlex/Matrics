import React, { useEffect, useState, useMemo } from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { listFriends } from '../../../services/social.js';
import { getUser } from '../../../services/users.js';
import { getUserInventoryForTrade, createTradeRequest } from '../../../services/trades.js';
import { Button, StateView } from '../../../components/ui/index.jsx';

function formatFriend(friendship, currentUserId) {
  const otherUserId = friendship.friend_id === currentUserId ? friendship.user_id : friendship.friend_id;
  return {
    id: friendship.id,
    friendUserId: otherUserId,
    status: friendship.status
  };
}

export function TradeModal({
  isOpen,
  onClose,
  currentUser,
  item,
  itemQuantity,
  onTradeCreated
}) {
  const [friendOptions, setFriendOptions] = useState([]);
  const [loadingFriends, setLoadingFriends] = useState(false);
  const [friendInventory, setFriendInventory] = useState([]);
  const [loadingInventory, setLoadingInventory] = useState(false);
  
  const [form, setForm] = useState({
    friendUserId: '',
    requestedItemId: '',
    requestedQuantity: '',
    initiatorQuantity: '',
    comment: ''
  });
  
  const [errors, setErrors] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setErrors(null);
      setFriendInventory([]);
      return;
    }
    
    if (item) {
      setForm((prev) => ({
        ...prev,
        initiatorQuantity: Math.min(prev.initiatorQuantity, itemQuantity)
      }));
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
  }, [isOpen, currentUser?.id, item, itemQuantity]);

  useEffect(() => {
    if (!isOpen || !form.friendUserId) {
      setFriendInventory([]);
      setForm((prev) => ({ ...prev, requestedItemId: '' }));
      return;
    }

    async function loadFriendInventory() {
      if (!currentUser?.id || !form.friendUserId) {
        return;
      }
      setLoadingInventory(true);
      try {
        const inventory = await getUserInventoryForTrade(currentUser.id, form.friendUserId);
        setFriendInventory(Array.isArray(inventory) ? inventory : []);
      } catch (error) {
        console.error('Ошибка загрузки инвентаря друга:', error);
        setFriendInventory([]);
      } finally {
        setLoadingInventory(false);
      }
    }
    loadFriendInventory();
  }, [isOpen, form.friendUserId, currentUser?.id]);

  useEffect(() => {
    if (!isOpen) {
      setForm({
        friendUserId: '',
        requestedItemId: '',
        requestedQuantity: '',
        initiatorQuantity: '',
        comment: ''
      });
    }
  }, [isOpen]);

  const canSubmit = useMemo(() => {
    if (!form.friendUserId) return false;
    const initiatorQty = Number(form.initiatorQuantity) || 0;
    const requestedQty = Number(form.requestedQuantity) || 0;
    if (!item && initiatorQty <= 0) return false;
    if (item && initiatorQty > itemQuantity) return false;
    if (form.requestedItemId && requestedQty <= 0) return false;
    return true;
  }, [form, item, itemQuantity]);

  const handleChange = (field, value) => {
    setForm((prev) => {
      const updated = { ...prev, [field]: value };
      // Если изменился друг, сбрасываем выбранный предмет
      if (field === 'friendUserId') {
        updated.requestedItemId = '';
        updated.requestedQuantity = 1;
      }
      // Если изменился запрашиваемый предмет, сбрасываем количество
      if (field === 'requestedItemId') {
        const selectedItem = friendInventory.find((inv) => inv.item_id === Number(value));
        updated.requestedQuantity = selectedItem ? String(Math.min(1, selectedItem.quantity)) : '';
      }
      return updated;
    });
  };

  const selectedRequestedItem = useMemo(() => {
    if (!form.requestedItemId) return null;
    return friendInventory.find((inv) => inv.item_id === Number(form.requestedItemId));
  }, [form.requestedItemId, friendInventory]);

  const maxRequestedQuantity = selectedRequestedItem ? selectedRequestedItem.quantity : 0;

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canSubmit || !currentUser?.id) {
      return;
    }
    setIsSubmitting(true);
    setErrors(null);
    try {
      const tradeData = {
        recipient_id: Number(form.friendUserId),
        initiator_item_id: item ? item.id : null,
        initiator_quantity: item ? (Number(form.initiatorQuantity) || 1) : 1,
        requested_item_id: form.requestedItemId ? Number(form.requestedItemId) : null,
        requested_quantity: form.requestedItemId ? (Number(form.requestedQuantity) || 1) : 1
      };
      const trimmedComment = (form.comment || '').trim();
      if (trimmedComment) {
        tradeData.comment = trimmedComment;
      }
      
      const trade = await createTradeRequest(currentUser.id, tradeData);
      if (onTradeCreated) {
        onTradeCreated(trade);
      }
      onClose();
    } catch (error) {
      setErrors(error.message ?? 'Не удалось создать предложение обмена');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={item ? 'Обменять предмет' : 'Отправить подарок'}>
      {loadingFriends ? (
        <StateView state="loading" message="Загружаем друзей…" compact />
      ) : friendOptions.length === 0 ? (
        <StateView
          state={errors ? 'error' : 'empty'}
          title={errors ? 'Не удалось загрузить друзей' : 'Пока некому отправить'}
          message={errors ?? 'Обмен доступен только с подтверждёнными друзьями.'}
          compact
        />
      ) : (
        <form onSubmit={handleSubmit} className="form-group fc-form">
          <div>
            <label htmlFor="tradeFriend">Выберите друга</label>
            <select
              id="tradeFriend"
              value={form.friendUserId}
              onChange={(event) => handleChange('friendUserId', event.target.value)}
            >
              <option value="">Выберите друга</option>
              {friendOptions.map((option) => (
                <option key={option.optionId} value={option.userId}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          {item && (
            <div>
              <label htmlFor="tradeInitiatorQuantity">Количество предметов для обмена</label>
              <input
                type="number"
                id="tradeInitiatorQuantity"
                min="1"
                max={itemQuantity}
                value={form.initiatorQuantity === 0 || form.initiatorQuantity === '0' ? '' : form.initiatorQuantity}
                onChange={(event) => handleChange('initiatorQuantity', event.target.value)}
              />
              <small className="fc-hint">Доступно: {itemQuantity}</small>
            </div>
          )}

          <div>
            <label htmlFor="tradeRequestedItem">
              Запросить предмет взамен (опционально)
            </label>
            {loadingInventory ? (
              <StateView state="loading" message="Загрузка инвентаря друга…" compact />
            ) : (
              <>
                <select
                  id="tradeRequestedItem"
                  value={form.requestedItemId}
                  onChange={(event) => handleChange('requestedItemId', event.target.value)}
                >
                  <option value="">Ничего — это подарок</option>
                  {friendInventory.map((invItem) => (
                    <option key={invItem.item_id} value={invItem.item_id}>
                      {`${invItem.item_name ?? `Предмет #${invItem.item_id}`} ×${invItem.quantity}`}
                    </option>
                  ))}
                </select>
                {friendInventory.length === 0 && form.friendUserId && (
                  <small className="fc-hint">У друга нет предметов в инвентаре</small>
                )}
              </>
            )}
          </div>

          {form.requestedItemId && selectedRequestedItem && (
            <div>
              <label htmlFor="tradeRequestedQuantity">Количество запрашиваемых предметов</label>
              <input
                type="number"
                id="tradeRequestedQuantity"
                min="1"
                max={maxRequestedQuantity}
                value={form.requestedQuantity === 0 || form.requestedQuantity === '0' ? '' : form.requestedQuantity}
                onChange={(event) => handleChange('requestedQuantity', event.target.value)}
              />
              <small className="fc-hint">Доступно у друга: {maxRequestedQuantity}</small>
            </div>
          )}

          <div>
            <label htmlFor="tradeComment">Комментарий (опционально)</label>
            <textarea
              id="tradeComment"
              maxLength={500}
              value={form.comment}
              onChange={(event) => handleChange('comment', event.target.value)}
              placeholder="Например: «Это для тебя» или условия обмена"
              rows={3}
            />
            <small className="fc-hint">До 500 символов</small>
          </div>

          {errors ? <div className="fc-form-error" role="alert">{errors}</div> : null}

          <div className="fc-form-actions fc-form-actions--pair">
            <Button variant="secondary" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" disabled={!canSubmit} loading={isSubmitting}>
              {form.requestedItemId ? 'Предложить обмен' : 'Отправить подарок'}
            </Button>
          </div>
        </form>
      )}
    </Modal>
  );
}

