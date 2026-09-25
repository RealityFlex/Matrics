import React from 'react';
import { Modal } from './Modal.jsx';
import { Button } from '../ui/index.jsx';
import { AlertTriangle, Info } from 'lucide-react';

const ICONS = { danger: AlertTriangle, warning: AlertTriangle, info: Info };

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmText = 'Да',
  cancelText = 'Отмена',
  type = 'warning',
}) {
  const handleConfirm = () => {
    if (onConfirm) {
      onConfirm();
    }
    onClose();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title || 'Подтверждение'}>
      <div className="dialog-body">
        <div className={`dialog-icon dialog-icon--${type}`} aria-hidden="true">
          {React.createElement(ICONS[type] ?? ICONS.info, { size: 28, strokeWidth: 2 })}
        </div>
        <p className="dialog-message">{message}</p>
        <div className="dialog-actions">
          <Button variant="secondary" onClick={onClose}>
            {cancelText}
          </Button>
          <Button variant={type === 'danger' ? 'danger' : 'primary'} onClick={handleConfirm}>
            {confirmText}
          </Button>
        </div>
      </div>
    </Modal>
  );
}
