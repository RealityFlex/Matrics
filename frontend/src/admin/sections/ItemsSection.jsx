import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { Modal } from '../../components/common/Modal.jsx';
import { adminApi, ITEM_RARITY_OPTIONS, ITEM_TYPE_OPTIONS } from '../api.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Button, StateView } from '../../components/ui/index.jsx';
import { StatValue } from '../../components/ui/icons.jsx';
import { ModalFormActions } from '../components/AdminBits.jsx';
import { ITEM_TYPE_LABELS, RARITY_LABELS } from '../labels.js';

const emptyItemForm = {
  id: null,
  name: '',
  description: '',
  rarity: ITEM_RARITY_OPTIONS[0].value,
  type: ITEM_TYPE_OPTIONS[0].value,
  base_price: ''
};

export function ItemsSection({ isActive }) {
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formState, setFormState] = useState(emptyItemForm);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, itemId: null });

  const loadItems = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.listItems();
      setItems(Array.isArray(data) ? data : []);
    } catch (loadError) {
      console.error('Ошибка загрузки предметов:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить предметы');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadItems();
    }
  }, [isActive, loadItems]);

  const rarityMap = useMemo(
    () =>
      ITEM_RARITY_OPTIONS.reduce(
        (acc, option) => {
          acc[option.value] = option.label;
          return acc;
        },
        { ...RARITY_LABELS }
      ),
    []
  );

  const typeMap = useMemo(
    () =>
      ITEM_TYPE_OPTIONS.reduce(
        (acc, option) => {
          acc[option.value] = option.label;
          return acc;
        },
        { ...ITEM_TYPE_LABELS }
      ),
    []
  );

  const handleOpenCreate = () => {
    setFormState(emptyItemForm);
    setIsModalOpen(true);
  };

  const handleOpenEdit = async (itemId) => {
    setIsSubmitting(true);
    try {
      const item = await adminApi.getItem(itemId);
      setFormState({
        id: item.id,
        name: item.name ?? '',
        description: item.description ?? '',
        rarity: item.rarity ?? ITEM_RARITY_OPTIONS[0].value,
        type: item.type ?? ITEM_TYPE_OPTIONS[0].value,
        base_price: item.base_price && item.base_price !== 0 ? String(item.base_price) : ''
      });
      setIsModalOpen(true);
    } catch (loadError) {
      console.error('Ошибка загрузки предмета:', loadError);
      setNotification({
        isOpen: true,
        message: loadError.message ?? 'Не удалось загрузить предмет',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setIsSubmitting(true);
    try {
      const payload = {
        name: formState.name.trim(),
        description: formState.description.trim() || null,
        rarity: formState.rarity,
        type: formState.type,
        base_price: formState.base_price ? Number(formState.base_price) : 0
      };

      if (!payload.name) {
        throw new Error('Название обязательно');
      }

      if (formState.id) {
        await adminApi.updateItem(formState.id, payload);
      } else {
        await adminApi.createItem(payload);
      }

      setIsModalOpen(false);
      setFormState(emptyItemForm);
      await loadItems();
    } catch (submitError) {
      console.error('Ошибка сохранения предмета:', submitError);
      setNotification({
        isOpen: true,
        message: submitError.message ?? 'Не удалось сохранить предмет',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (itemId) => {
    setDeleteConfirm({ isOpen: true, itemId });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.itemId) return;
    try {
      await adminApi.deleteItem(deleteConfirm.itemId);
      await loadItems();
      setDeleteConfirm({ isOpen: false, itemId: null });
    } catch (deleteError) {
      console.error('Ошибка удаления предмета:', deleteError);
      setNotification({
        isOpen: true,
        message: deleteError.message ?? 'Не удалось удалить предмет',
        type: 'error',
        title: 'Ошибка'
      });
      setDeleteConfirm({ isOpen: false, itemId: null });
    }
  };

  return (
    <section id="items-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Управление предметами</h2>
        <Button size="sm" icon={<Plus size={16} aria-hidden="true" />} onClick={handleOpenCreate} disabled={isSubmitting}>
          Создать предмет
        </Button>
      </div>
      <div className="table-container">
        {isLoading ? (
          <StateView state="loading" message="Загрузка предметов…" />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить предметы" message={error} onRetry={loadItems} />
        ) : !items.length ? (
          <StateView state="empty" title="Предметов пока нет" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Название</th>
                <th>Описание</th>
                <th>Редкость</th>
                <th>Тип</th>
                <th>Цена</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id}>
                  <td>{item.id}</td>
                  <td>{item.name}</td>
                  <td>{item.description || '—'}</td>
                  <td>{rarityMap[item.rarity] ?? 'Другая'}</td>
                  <td>{typeMap[item.type] ?? 'Другой'}</td>
                  <td>
                    <span className="admin-inline">
                      <StatValue kind="coins" value={item.base_price ?? 0} />
                    </span>
                  </td>
                  <td>
                    <div className="action-buttons">
                      <Button size="sm" variant="secondary" onClick={() => handleOpenEdit(item.id)}>
                        Редактировать
                      </Button>
                      <Button size="sm" variant="danger" onClick={() => handleDelete(item.id)}>
                        Удалить
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          if (!isSubmitting) {
            setIsModalOpen(false);
            setFormState(emptyItemForm);
          }
        }}
        title={formState.id ? 'Редактировать предмет' : 'Создать предмет'}
        footer={
          <ModalFormActions
            formId="admin-item-form"
            isSubmitting={isSubmitting}
            onCancel={() => {
              if (!isSubmitting) {
                setIsModalOpen(false);
                setFormState(emptyItemForm);
              }
            }}
          />
        }
      >
        <form id="admin-item-form" className="admin-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="item-name">Название *</label>
            <input
              id="item-name"
              type="text"
              value={formState.name}
              onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
              required
              disabled={isSubmitting}
            />
          </div>
          <div className="form-group">
            <label htmlFor="item-description">Описание</label>
            <textarea
              id="item-description"
              rows={3}
              value={formState.description}
              onChange={(event) => setFormState((prev) => ({ ...prev, description: event.target.value }))}
              disabled={isSubmitting}
            />
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="item-rarity">Редкость *</label>
              <select
                id="item-rarity"
                value={formState.rarity}
                onChange={(event) => setFormState((prev) => ({ ...prev, rarity: event.target.value }))}
                required
                disabled={isSubmitting}
              >
                {ITEM_RARITY_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label htmlFor="item-type">Тип *</label>
              <select
                id="item-type"
                value={formState.type}
                onChange={(event) => setFormState((prev) => ({ ...prev, type: event.target.value }))}
                required
                disabled={isSubmitting}
              >
                {ITEM_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="form-group">
            <label htmlFor="item-price">Базовая цена *</label>
            <input
              id="item-price"
              type="number"
              min="0"
              value={formState.base_price === 0 || formState.base_price === '0' ? '' : formState.base_price}
              onChange={(event) => setFormState((prev) => ({ ...prev, base_price: event.target.value }))}
              required
              disabled={isSubmitting}
            />
          </div>
        </form>
        </Modal>
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
      <ConfirmModal
        isOpen={deleteConfirm.isOpen}
        onClose={() => setDeleteConfirm({ isOpen: false, itemId: null })}
        onConfirm={handleDeleteConfirm}
        title="Удаление предмета"
        message="Удалить предмет?"
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />
    </section>
  );
}


