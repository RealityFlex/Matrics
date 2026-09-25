import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Plus } from 'lucide-react';
import { Modal } from '../../components/common/Modal.jsx';
import { adminApi } from '../api.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';
import { StatValue } from '../../components/ui/icons.jsx';
import { ModalFormActions } from '../components/AdminBits.jsx';

const emptyListing = {
  id: null,
  item_id: '',
  price: 0,
  stock: '',
  is_active: true
};

export function ShopSection({ isActive }) {
  const [listings, setListings] = useState([]);
  const [items, setItems] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [formState, setFormState] = useState(emptyListing);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [deleteConfirm, setDeleteConfirm] = useState({ isOpen: false, listingId: null });

  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [listingsResponse, itemsResponse] = await Promise.all([
        adminApi.listShopListings(),
        adminApi.listItems()
      ]);
      setListings(Array.isArray(listingsResponse) ? listingsResponse : []);
      setItems(Array.isArray(itemsResponse) ? itemsResponse : []);
    } catch (loadError) {
      console.error('Ошибка загрузки магазина:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить магазин');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadData();
    }
  }, [isActive, loadData]);

  const itemsMap = useMemo(
    () =>
      items.reduce((acc, item) => {
        acc[item.id] = item;
        return acc;
      }, {}),
    [items]
  );

  const handleOpenCreate = () => {
    setFormState(emptyListing);
    setIsModalOpen(true);
  };

  const handleOpenEdit = async (listingId) => {
    setIsSubmitting(true);
    try {
      const listing = await adminApi.getShopListing(listingId);
      setFormState({
        id: listing.id,
        item_id: listing.item_id ?? '',
        price: listing.price ?? 0,
        stock: listing.stock ?? '',
        is_active: Boolean(listing.is_active)
      });
      setIsModalOpen(true);
    } catch (loadError) {
      console.error('Ошибка загрузки товара магазина:', loadError);
      setNotification({
        isOpen: true,
        message: loadError.message ?? 'Не удалось загрузить товар',
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
        item_id: Number(formState.item_id),
        price: Number(formState.price) || 0,
        stock: formState.stock === '' ? null : Number(formState.stock),
        is_active: Boolean(formState.is_active)
      };

      if (!payload.item_id) {
        throw new Error('Выберите предмет');
      }

      if (formState.id) {
        await adminApi.updateShopListing(formState.id, payload);
      } else {
        await adminApi.createShopListing(payload);
      }

      setIsModalOpen(false);
      setFormState(emptyListing);
      await loadData();
    } catch (submitError) {
      console.error('Ошибка сохранения товара магазина:', submitError);
      setNotification({
        isOpen: true,
        message: submitError.message ?? 'Не удалось сохранить товар',
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (listingId) => {
    setDeleteConfirm({ isOpen: true, listingId });
  };

  const handleDeleteConfirm = async () => {
    if (!deleteConfirm.listingId) return;
    try {
      await adminApi.deleteShopListing(deleteConfirm.listingId);
      await loadData();
      setDeleteConfirm({ isOpen: false, listingId: null });
    } catch (deleteError) {
      console.error('Ошибка удаления товара магазина:', deleteError);
      setNotification({
        isOpen: true,
        message: deleteError.message ?? 'Не удалось удалить товар',
        type: 'error',
        title: 'Ошибка'
      });
      setDeleteConfirm({ isOpen: false, listingId: null });
    }
  };

  return (
    <section id="shop-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Управление магазином</h2>
        <Button size="sm" icon={<Plus size={16} aria-hidden="true" />} onClick={handleOpenCreate} disabled={isSubmitting}>
          Добавить товар
        </Button>
      </div>
      <div className="table-container">
        {isLoading ? (
          <StateView state="loading" message="Загрузка магазина…" />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить магазин" message={error} onRetry={loadData} />
        ) : !listings.length ? (
          <StateView state="empty" title="Товаров пока нет" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Предмет</th>
                <th>Цена</th>
                <th>Остаток</th>
                <th>Активен</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {listings.map((listing) => {
                const item = itemsMap[listing.item_id];
                return (
                  <tr key={listing.id}>
                    <td>{listing.id}</td>
                    <td>{item ? item.name : `ID ${listing.item_id}`}</td>
                    <td>
                      <span className="admin-inline">
                        <StatValue kind="coins" value={listing.price ?? 0} />
                      </span>
                    </td>
                    <td>{listing.stock ?? 'Без ограничений'}</td>
                    <td>
                      {listing.is_active ? <Badge tone="success">Да</Badge> : <Badge>Нет</Badge>}
                    </td>
                    <td>
                      <div className="action-buttons">
                        <Button size="sm" variant="secondary" onClick={() => handleOpenEdit(listing.id)}>
                          Редактировать
                        </Button>
                        <Button size="sm" variant="danger" onClick={() => handleDelete(listing.id)}>
                          Удалить
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          if (!isSubmitting) {
            setIsModalOpen(false);
            setFormState(emptyListing);
          }
        }}
        title={formState.id ? 'Редактировать товар' : 'Добавить товар'}
        footer={
          <ModalFormActions
            formId="admin-shop-form"
            isSubmitting={isSubmitting}
            onCancel={() => {
              if (!isSubmitting) {
                setIsModalOpen(false);
                setFormState(emptyListing);
              }
            }}
          />
        }
      >
        <form id="admin-shop-form" className="admin-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="shop-item">Предмет *</label>
            <select
              id="shop-item"
              value={formState.item_id}
              onChange={(e) => setFormState((prev) => ({ ...prev, item_id: e.target.value }))}
              required
              disabled={isSubmitting}
            >
              <option value="">Выберите предмет...</option>
              {items.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </div>
          <div className="form-row">
            <div className="form-group">
              <label htmlFor="shop-price">Цена *</label>
              <input
                id="shop-price"
                type="number"
                min="0"
                value={formState.price}
                onChange={(e) => setFormState((prev) => ({ ...prev, price: e.target.value }))}
                required
                disabled={isSubmitting}
              />
            </div>
            <div className="form-group">
              <label htmlFor="shop-stock">Остаток</label>
              <input
                id="shop-stock"
                type="number"
                min="1"
                value={formState.stock}
                onChange={(e) => setFormState((prev) => ({ ...prev, stock: e.target.value }))}
                placeholder="Без ограничений"
                disabled={isSubmitting}
              />
            </div>
          </div>
          <div className="form-group checkbox-group">
            <label htmlFor="shop-active">
              <input
                id="shop-active"
                type="checkbox"
                checked={formState.is_active}
                onChange={(e) => setFormState((prev) => ({ ...prev, is_active: e.target.checked }))}
                disabled={isSubmitting}
              />
              Активен
            </label>
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
        onClose={() => setDeleteConfirm({ isOpen: false, listingId: null })}
        onConfirm={handleDeleteConfirm}
        title="Удаление товара"
        message="Удалить товар?"
        confirmText="Удалить"
        cancelText="Отмена"
        type="danger"
      />
    </section>
  );
}


