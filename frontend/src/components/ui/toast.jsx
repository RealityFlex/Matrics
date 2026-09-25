/**
 * Глобальные уведомления (тосты). Использование из любого места:
 *   import { toast } from '../components/ui/toast.jsx';
 *   toast.success('Посещение отмечено', '+5 монет');
 * Виджет <ToastViewport /> монтируется один раз в корне приложения.
 */
import React, { useEffect, useState } from 'react';
import { AlertTriangle, CheckCircle2, Gift, Info } from 'lucide-react';

const listeners = new Set();
let counter = 0;

function emit(kind, title, message, options = {}) {
  const item = {
    id: ++counter,
    kind,
    title,
    message,
    duration: options.duration ?? (kind === 'error' ? 6000 : 3500)
  };
  listeners.forEach((listener) => listener(item));
  return item.id;
}

export const toast = {
  success: (title, message, options) => emit('success', title, message, options),
  error: (title, message, options) => emit('error', title, message, options),
  info: (title, message, options) => emit('info', title, message, options),
  reward: (title, message, options) => emit('reward', title, message, options)
};

const ICONS = { success: CheckCircle2, error: AlertTriangle, info: Info, reward: Gift };

export function ToastViewport() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    const listener = (item) => {
      setItems((prev) => [...prev.slice(-2), item]);
      window.setTimeout(() => {
        setItems((prev) => prev.filter((candidate) => candidate.id !== item.id));
      }, item.duration);
    };
    listeners.add(listener);
    return () => listeners.delete(listener);
  }, []);

  const dismiss = (id) => setItems((prev) => prev.filter((item) => item.id !== id));

  return (
    <div className="ui-toasts" aria-live="polite" aria-atomic="false">
      {items.map((item) => (
        <div key={item.id} className={`ui-toast ui-toast--${item.kind}`} role={item.kind === 'error' ? 'alert' : 'status'}>
          <span className="ui-toast__icon" aria-hidden="true">{React.createElement(ICONS[item.kind] ?? Info, { size: 20 })}</span>
          <div className="ui-toast__body">
            {item.title ? <div className="ui-toast__title">{item.title}</div> : null}
            {item.message ? <div className="ui-toast__message">{item.message}</div> : null}
          </div>
          <button type="button" className="ui-toast__close" aria-label="Закрыть" onClick={() => dismiss(item.id)}>
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
