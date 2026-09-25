import React, { useEffect, useState, useMemo } from 'react';
import { Modal } from '../../../components/common/Modal.jsx';
import { createShopListing } from '../../../services/shop.js';
import { Button } from '../../../components/ui/index.jsx';

export function ListItemModal({
  isOpen,
  onClose,
  currentUser,
  item,
  itemQuantity,
  onListingCreated
}) {
  const [form, setForm] = useState({
    price: '',
    stock: ''
  });
  
  const [errors, setErrors] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!isOpen) {
      setErrors(null);
      return;
    }
    
    if (item) {
      setForm({
        price: item.base_price && item.base_price !== 0 ? String(item.base_price) : '',
        stock: String(Math.min(1, itemQuantity))
      });
    }
  }, [isOpen, item, itemQuantity]);

  const canSubmit = useMemo(() => {
    if (!item || !currentUser?.id) return false;
    const price = Number(form.price) || 0;
    const stock = Number(form.stock) || 0;
    if (price < 0) return false;
    if (stock < 1 || stock > itemQuantity) return false;
    return true;
  }, [form, item, itemQuantity, currentUser?.id]);

  const handleChange = (field, value) => {
    setForm((prev) => {
      const updated = { ...prev, [field]: value };
      // Ограничиваем stock максимальным количеством
      if (field === 'stock') {
        const numValue = Number(value) || 0;
        if (numValue > itemQuantity) {
          updated.stock = String(itemQuantity);
        }
      }
      return updated;
    });
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!canSubmit || !currentUser?.id || !item) {
      return;
    }
    setIsSubmitting(true);
    setErrors(null);
    try {
      const listingData = {
        seller_id: currentUser.id,
        item_id: item.id,
        price: Number(form.price),
        stock: Number(form.stock),
        is_active: true
      };
      
      const listing = await createShopListing(listingData);
      if (onListingCreated) {
        onListingCreated(listing);
      }
      onClose();
    } catch (error) {
      setErrors(error.message ?? 'Не удалось выложить предмет в магазин');
    } finally {
      setIsSubmitting(false);
    }
  };

  if (!item) {
    return null;
  }

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Выложить предмет в магазин">
      <form onSubmit={handleSubmit} className="form-group fc-form">
        <div>
          <label htmlFor="listItemName">Предмет</label>
          <input
            type="text"
            id="listItemName"
            value={item.name || `Предмет #${item.id}`}
            disabled
          />
        </div>

        <div>
          <label htmlFor="listItemPrice">Цена (монеты)</label>
          <input
            type="number"
            id="listItemPrice"
            min="0"
            value={form.price === 0 || form.price === '0' ? '' : form.price}
            onChange={(event) => handleChange('price', event.target.value)}
          />
        </div>

        <div>
          <label htmlFor="listItemStock">Количество</label>
          <input
            type="number"
            id="listItemStock"
            min="1"
            max={itemQuantity}
            value={form.stock === 0 || form.stock === '0' ? '' : form.stock}
            onChange={(event) => handleChange('stock', event.target.value)}
          />
          <small className="fc-hint">Доступно: {itemQuantity}</small>
        </div>

        {errors ? <div className="fc-form-error" role="alert">{errors}</div> : null}

        <div className="fc-form-actions fc-form-actions--pair">
          <Button variant="secondary" onClick={onClose}>
            Отмена
          </Button>
          <Button type="submit" disabled={!canSubmit} loading={isSubmitting}>
            Выставить на продажу
          </Button>
        </div>
      </form>
    </Modal>
  );
}

