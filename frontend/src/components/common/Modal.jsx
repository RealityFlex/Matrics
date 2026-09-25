import React, { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { maxBackButton } from '../../utils/maxBridge.js';

/**
 * Модальное окно на CSS-классах дизайн-системы.
 * Закрывается кнопкой ×, кликом по фону, клавишей Esc и системной кнопкой «Назад» MAX.
 */
export function Modal({ isOpen, onClose = null, title, children, footer, size = 'md' }) {
  useEffect(() => {
    if (!isOpen) {
      return undefined;
    }
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    const handleKey = (event) => {
      if (event.key === 'Escape' && onClose) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKey);
    const releaseBack = onClose ? maxBackButton.push(onClose) : null;

    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener('keydown', handleKey);
      if (releaseBack) {
        releaseBack();
      }
    };
  }, [isOpen, onClose]);

  if (!isOpen) {
    return null;
  }

  const handleOverlayClick = (event) => {
    if (event.target === event.currentTarget && onClose) {
      onClose();
    }
  };

  return createPortal(
    <div className="ui-modal-overlay" onMouseDown={handleOverlayClick} role="presentation">
      <div className={`ui-modal ui-modal--${size}`} role="dialog" aria-modal="true" aria-label={typeof title === 'string' ? title : undefined}>
        <div className="ui-modal__header">
          <h3 className="ui-modal__title">{title}</h3>
          {onClose ? (
            <button type="button" className="ui-modal__close" onClick={onClose} aria-label="Закрыть">
              ×
            </button>
          ) : null}
        </div>
        <div className="ui-modal__body">{children}</div>
        {footer ? <div className="ui-modal__footer">{footer}</div> : null}
      </div>
    </div>,
    document.body
  );
}
