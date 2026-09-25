import React, { useCallback, useEffect, useState } from 'react';
import { useAppState, useAppDispatch } from '../../state/AppProvider.jsx';
import { getUserInventory, useInventoryItem } from '../../services/inventory.js';
import {
  getReceivedTradeRequests,
  getSentTradeRequests,
  acceptTradeRequest,
  rejectTradeRequest,
  cancelTradeRequest
} from '../../services/trades.js';
import { InventoryList } from './components/InventoryList.jsx';
import { TradeRequestCard } from './components/TradeRequestCard.jsx';
import { TradeModal } from './components/TradeModal.jsx';
import { ListItemModal } from './components/ListItemModal.jsx';
import { LootboxButton } from './components/LootboxButton.jsx';
import { getUser } from '../../services/users.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { toast } from '../../components/ui/toast.jsx';
import { StateView } from '../../components/ui/index.jsx';
import { RewardChips } from '../../components/ui/icons.jsx';
import '../../styles/features-core.css';
import {
  getItemIcon,
  getRarityColor,
  getRarityLabel,
  getTypeLabel
} from '../../utils/itemPresentation.js';

export function InventorySection({ isActive }) {
  const { user, inventorySyncVersion } = useAppState();
  const dispatch = useAppDispatch();

  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [tradeRequests, setTradeRequests] = useState([]);
  const [isLoadingTrades, setIsLoadingTrades] = useState(false);
  const [tradeError, setTradeError] = useState(null);
  const [processingTradeId, setProcessingTradeId] = useState(null);

  const [tradeModalOpen, setTradeModalOpen] = useState(false);
  const [tradeModalItem, setTradeModalItem] = useState(null);
  const [tradeModalQuantity, setTradeModalQuantity] = useState(0);

  const [listItemModalOpen, setListItemModalOpen] = useState(false);
  const [listItemModalItem, setListItemModalItem] = useState(null);
  const [listItemModalQuantity, setListItemModalQuantity] = useState(0);
  const [usingItemId, setUsingItemId] = useState(null);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });

  const loadInventory = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    setIsLoading(true);
    setError(null);
    try {
      const inventory = await getUserInventory(user.id);
      
      // Группируем предметы по item_id и суммируем quantity
      const grouped = new Map();
      (inventory || []).forEach((userItem) => {
        const item = userItem.item || {};
        const itemId = item.id ?? userItem.item_id;
        
        if (itemId) {
          if (!grouped.has(itemId)) {
            const type = item.type || 'special';
            const rarity = item.rarity || 'common';
            grouped.set(itemId, {
              uniqueKey: `item-${itemId}`,
              item,
              quantity: 0,
              icon: getItemIcon(type, itemId),
              rarityColor: getRarityColor(rarity),
              rarityLabel: getRarityLabel(rarity),
              typeLabel: getTypeLabel(type)
            });
          }
          // Суммируем quantity для одинаковых item_id
          grouped.get(itemId).quantity += userItem.quantity || 1;
        }
      });
      
      const mapped = Array.from(grouped.values());
      setItems(mapped);
    } catch (loadError) {
      console.error('Ошибка загрузки инвентаря:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить инвентарь');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  const loadTradeRequests = useCallback(async () => {
    if (!user?.id) {
      return;
    }
    setIsLoadingTrades(true);
    setTradeError(null);
    try {
      const [received, sent] = await Promise.all([
        getReceivedTradeRequests(user.id),
        getSentTradeRequests(user.id)
      ]);
      // Объединяем входящие и исходящие обмены
      const allRequests = [
        ...(Array.isArray(received) ? received : []),
        ...(Array.isArray(sent) ? sent : [])
      ];
      setTradeRequests(allRequests);
      const hasIncomingPending = allRequests.some(
        (request) => request.status === 'pending' && request.recipient_id === user.id
      );
      if (!hasIncomingPending) {
        dispatch({ type: 'CLEAR_BADGE', key: 'inventory' });
      }
    } catch (loadError) {
      console.error('Ошибка загрузки предложений обмена:', loadError);
      setTradeError(loadError.message ?? 'Не удалось загрузить предложения обмена');
    } finally {
      setIsLoadingTrades(false);
    }
  }, [user?.id, dispatch]);

  useEffect(() => {
    if (isActive && user?.id) {
      loadInventory();
      loadTradeRequests();
    }
  }, [isActive, user?.id, inventorySyncVersion]); // Убрали loadInventory и loadTradeRequests из зависимостей

  const handleTrade = useCallback((item, quantity) => {
    setTradeModalItem(item);
    setTradeModalQuantity(quantity);
    setTradeModalOpen(true);
  }, []);

  const handleListInShop = useCallback((item, quantity) => {
    setListItemModalItem(item);
    setListItemModalQuantity(quantity);
    setListItemModalOpen(true);
  }, []);

  const handleUseItem = useCallback(async (item) => {
    if (!user?.id || !item?.id) {
      return;
    }

    setUsingItemId(item.id);
    try {
      await useInventoryItem(user.id, item.id);
      const reward = item.item ?? item;
      toast.reward(
        'Предмет использован',
        <>
          {reward.name ?? ''}
          <RewardChips
            rewards={{
              coins: reward.reward_coins ?? 0,
              intelligence: reward.reward_intelligence_points ?? 0,
              satisfaction: reward.reward_satisfaction ?? 0
            }}
          />
        </>
      );
      await loadInventory();
    } catch (error) {
      console.error('Ошибка использования предмета:', error);
      setNotification({
        isOpen: true,
        message: `Не удалось использовать предмет: ${error.message ?? 'Неизвестная ошибка'}`,
        type: 'error',
        title: 'Ошибка'
      });
      await loadInventory();
    } finally {
      setUsingItemId(null);
    }
  }, [user?.id, loadInventory]);

  const handleTradeCreated = useCallback(() => {
    loadInventory();
    loadTradeRequests();
  }, [loadInventory, loadTradeRequests]);

  const handleListingCreated = useCallback(() => {
    loadInventory();
  }, [loadInventory]);

  const handleAcceptTrade = useCallback(async (tradeId) => {
    setProcessingTradeId(tradeId);
    try {
      await acceptTradeRequest(tradeId);
      await loadInventory();
      await loadTradeRequests();
    } catch (error) {
      console.error('Ошибка принятия обмена:', error);
      setTradeError(error.message ?? 'Не удалось принять предложение обмена');
    } finally {
      setProcessingTradeId(null);
    }
  }, [loadInventory, loadTradeRequests]);

  const handleRejectTrade = useCallback(async (tradeId) => {
    setProcessingTradeId(tradeId);
    try {
      await rejectTradeRequest(tradeId);
      await loadInventory();
      await loadTradeRequests();
    } catch (error) {
      console.error('Ошибка отклонения обмена:', error);
      setTradeError(error.message ?? 'Не удалось отклонить предложение обмена');
    } finally {
      setProcessingTradeId(null);
    }
  }, [loadInventory, loadTradeRequests]);

  const handleCancelTrade = useCallback(async (tradeId) => {
    setProcessingTradeId(tradeId);
    try {
      await cancelTradeRequest(tradeId, user.id);
      await loadInventory();
      await loadTradeRequests();
    } catch (error) {
      console.error('Ошибка отмены обмена:', error);
      setTradeError(error.message ?? 'Не удалось отменить предложение обмена');
    } finally {
      setProcessingTradeId(null);
    }
  }, [user?.id, loadInventory, loadTradeRequests]);

  const handleLootboxOpened = useCallback(async (result) => {
    // Обновить инвентарь
    await loadInventory();
    
    // Обновить баланс монет пользователя
    if (user?.id && result?.remaining_coins !== undefined) {
      try {
        const updatedUser = await getUser(user.id);
        if (updatedUser) {
          dispatch({ type: 'SET_USER', user: updatedUser });
        }
      } catch (error) {
        console.error('Ошибка обновления баланса монет:', error);
        // Обновляем вручную из результата
        if (result.remaining_coins !== undefined) {
          dispatch({
            type: 'SET_USER',
            user: { ...user, coins: result.remaining_coins }
          });
        }
      }
    }
  }, [user, loadInventory, dispatch]);

  const pendingTrades = tradeRequests.filter((tr) => tr.status === 'pending');

  return (
    <div>
      <div className="section-header">
        <h2>Инвентарь</h2>
      </div>

      <LootboxButton onLootboxOpened={handleLootboxOpened} />

      {pendingTrades.length > 0 && (
        <div className="fc-block">
          <h3 className="section-subtitle">Предложения обмена</h3>
          {tradeError ? (
            <div className="inline-error" role="alert">{tradeError}</div>
          ) : null}
          {isLoadingTrades ? (
            <StateView state="loading" message="Загрузка предложений…" compact />
          ) : (
            <div className="cards-list">
              {pendingTrades.map((tradeRequest) => (
                <TradeRequestCard
                  key={tradeRequest.id}
                  tradeRequest={tradeRequest}
                  currentUserId={user?.id}
                  onAccept={handleAcceptTrade}
                  onReject={handleRejectTrade}
                  onCancel={handleCancelTrade}
                  isProcessing={processingTradeId === tradeRequest.id}
                />
              ))}
            </div>
          )}
        </div>
      )}

      <InventoryList
        items={items}
        isLoading={isLoading}
        error={error}
        onRetry={loadInventory}
        onTrade={handleTrade}
        onListInShop={handleListInShop}
        onUse={handleUseItem}
        usingItemId={usingItemId}
      />

      <TradeModal
        isOpen={tradeModalOpen}
        onClose={() => setTradeModalOpen(false)}
        currentUser={user}
        item={tradeModalItem}
        itemQuantity={tradeModalQuantity}
        onTradeCreated={handleTradeCreated}
      />

      <ListItemModal
        isOpen={listItemModalOpen}
        onClose={() => setListItemModalOpen(false)}
        currentUser={user}
        item={listItemModalItem}
        itemQuantity={listItemModalQuantity}
        onListingCreated={handleListingCreated}
      />
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
    </div>
  );
}

