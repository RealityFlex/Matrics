import React, { useState } from 'react';
import { useAppState } from '../../../state/AppProvider.jsx';
import { openLootbox } from '../../../services/lootbox.js';
import { LootboxModal } from './LootboxModal.jsx';
import { NotificationModal } from '../../../components/common/NotificationModal.jsx';
import { Gift } from 'lucide-react';
import { Button } from '../../../components/ui/index.jsx';
import { StatValue } from '../../../components/ui/icons.jsx';

const LOOTBOX_COST = 10;

export function LootboxButton({ onLootboxOpened }) {
  const { user } = useAppState();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isOpening, setIsOpening] = useState(false);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });

  const handleOpenLootbox = async () => {
    if (!user?.id) {
      setNotification({
        isOpen: true,
        message: 'Ошибка: пользователь не найден',
        type: 'error',
        title: 'Ошибка'
      });
      return;
    }

    if (user.coins < LOOTBOX_COST) {
      setNotification({
        isOpen: true,
        message: `Недостаточно монет. Требуется: ${LOOTBOX_COST}, доступно: ${user.coins}`,
        type: 'warning',
        title: 'Недостаточно монет'
      });
      return;
    }

    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
  };

  const handleLootboxResult = (result) => {
    if (onLootboxOpened) {
      onLootboxOpened(result);
    }
  };

  const handleOpenAnother = () => {
    // Закрываем текущее модальное окно и открываем новое
    setIsModalOpen(false);
    // Небольшая задержка для плавного перехода
    setTimeout(() => {
      setIsModalOpen(true);
    }, 300);
  };

  const coins = Number(user?.coins ?? 0);
  const canAfford = coins >= LOOTBOX_COST;

  return (
    <>
      <div className="lootbox-cta">
        <Button
          size="lg"
          block
          icon={<Gift size={20} />}
          onClick={handleOpenLootbox}
          disabled={!canAfford || isOpening}
          aria-describedby={!canAfford ? 'lootboxHint' : undefined}
        >
          Открыть лутбокс
          <span className="lootbox-cta__price">
            <StatValue kind="coins" value={LOOTBOX_COST} />
          </span>
        </Button>
        {!canAfford ? (
          <p className="lootbox-cta__hint" id="lootboxHint">
            Нужно {LOOTBOX_COST} монет — у вас {coins}
          </p>
        ) : null}
      </div>

      <LootboxModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        userId={user?.id}
        onResult={handleLootboxResult}
        onOpenAnother={handleOpenAnother}
      />
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
    </>
  );
}

