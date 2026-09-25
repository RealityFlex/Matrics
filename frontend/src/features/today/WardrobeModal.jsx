import React, { useCallback, useEffect, useState } from 'react';
import { Modal } from '../../components/common/Modal.jsx';
import { Badge, Button, ProgressBar, StateView } from '../../components/ui/index.jsx';
import { equipAppearance, getAppearanceCatalog, purchaseAppearance } from '../../services/characters.js';
import { toast } from '../../components/ui/toast.jsx';
import { Lock } from 'lucide-react';
import { StatValue } from '../../components/ui/icons.jsx';

const TABS = [
  { id: 'characters', label: 'Образ' },
  { id: 'environments', label: 'Локация' }
];

function unlockHint(item) {
  if (item.unlock_type === 'coins') return <StatValue kind="coins" value={item.price_coins ?? 0} size={14} />;
  const { current, required } = item.progress ?? {};
  return `${item.unlock_label}: ${Math.min(current ?? 0, required ?? 0)}/${required ?? 0}`;
}

/**
 * Гардероб: сеты внешности и окружения. Часть открывается за учебную активность
 * (посещения, серия, задачи, уровень), часть — за монеты.
 */
export function WardrobeModal({ isOpen, onClose, userId, coins, onChanged }) {
  const [tab, setTab] = useState('characters');
  const [catalog, setCatalog] = useState(null);
  const [state, setState] = useState('loading');
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    setState('loading');
    try {
      setCatalog(await getAppearanceCatalog(userId));
      setState('ready');
    } catch {
      setState('error');
    }
  }, [userId]);

  useEffect(() => {
    if (isOpen) load();
  }, [isOpen, load]);

  const handleEquip = async (item) => {
    setBusyId(item.id);
    try {
      const result = await equipAppearance(userId, item.id);
      toast.success('Готово', item.kind === 'character' ? `Образ «${item.name}» выбран` : `Локация «${item.name}» выбрана`);
      onChanged?.(result);
      await load();
    } catch (error) {
      toast.error('Не удалось применить', error?.message);
    } finally {
      setBusyId(null);
    }
  };

  const handleBuy = async (item) => {
    setBusyId(item.id);
    try {
      await purchaseAppearance(userId, item.id);
      toast.reward('Покупка', `«${item.name}» теперь ваш`);
      onChanged?.();
      await load();
    } catch (error) {
      toast.error('Покупка не удалась', error?.message);
    } finally {
      setBusyId(null);
    }
  };

  const items = catalog?.[tab] ?? [];

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Гардероб" size="lg">
      <div className="segmented" role="tablist" aria-label="Тип сета">
        {TABS.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={`segmented__item ${tab === item.id ? 'is-active' : ''}`}
            onClick={() => setTab(item.id)}
          >
            {item.label}
          </button>
        ))}
      </div>
      <p className="wardrobe__hint">Новые образы открываются за посещённые пары, серию без пропусков и выполненные задачи.</p>

      {state === 'loading' ? <StateView state="loading" message="Загружаем гардероб…" compact /> : null}
      {state === 'error' ? <StateView state="error" title="Гардероб не загрузился" onRetry={load} compact /> : null}

      {state === 'ready' ? (
        <div className="wardrobe__grid">
          {items.map((item) => {
            const canBuy = !item.unlocked && item.unlock_type === 'coins';
            const affordable = canBuy && (coins ?? 0) >= (item.price_coins ?? 0);
            return (
              <div key={item.id} className={`wardrobe-item ${item.equipped ? 'is-equipped' : ''} ${item.unlocked ? '' : 'is-locked'}`}>
                <div className="wardrobe-item__head">
                  <span className="wardrobe-item__name">{item.name}</span>
                  {item.equipped ? <Badge tone="success">Выбрано</Badge> : !item.unlocked ? <Badge tone="neutral" title="Закрыто">
                      <Lock size={14} aria-hidden="true" />
                      <span className="visually-hidden">Закрыто</span>
                    </Badge> : null}
                </div>
                {item.description ? <div className="wardrobe-item__desc">{item.description}</div> : null}
                {!item.unlocked && item.unlock_type !== 'coins' ? (
                  <ProgressBar value={Math.min(item.progress.current, item.progress.required)} max={item.progress.required || 1} tone="reward" />
                ) : null}
                <div className="wardrobe-item__footer">
                  {!item.unlocked ? <span className="wardrobe-item__req">{unlockHint(item)}</span> : <span />}
                  {item.unlocked && !item.equipped ? (
                    <Button size="sm" loading={busyId === item.id} onClick={() => handleEquip(item)}>
                      Выбрать
                    </Button>
                  ) : null}
                  {canBuy ? (
                    <Button size="sm" variant="secondary" loading={busyId === item.id} disabled={!affordable} onClick={() => handleBuy(item)}>
                      {affordable ? 'Купить' : 'Не хватает монет'}
                    </Button>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </Modal>
  );
}
