import React, { useEffect } from 'react';
import { Modal } from './Modal.jsx';
import { Button } from '../ui/index.jsx';
import { AlertTriangle, CheckCircle2, Info, XCircle } from 'lucide-react';

const ICONS = { success: CheckCircle2, error: XCircle, warning: AlertTriangle, info: Info };

export function NotificationModal({ isOpen, onClose, title, message, type = 'info' }) {
  useEffect(() => {
    if (isOpen && type === 'success') {
      // Успешные сообщения закрываются автоматически через 3 секунды
      const timer = setTimeout(() => {
        onClose();
      }, 3000);
      return () => clearTimeout(timer);
    }
  }, [isOpen, type, onClose]);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title || 'Уведомление'}>
      <div className="dialog-body" role={type === 'error' ? 'alert' : 'status'}>
        <div className={`dialog-icon dialog-icon--${type}`} aria-hidden="true">
          {React.createElement(ICONS[type] ?? ICONS.info, { size: 28, strokeWidth: 2 })}
        </div>
        <p className="dialog-message">{message}</p>
        <div className="dialog-actions">
          <Button onClick={onClose}>Понятно</Button>
        </div>
      </div>
    </Modal>
  );
}
