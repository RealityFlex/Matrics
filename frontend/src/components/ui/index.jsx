/**
 * UI-кит «Матрикс»: базовые компоненты единого визуального языка (см. docs/DESIGN.md).
 */
import React from 'react';
import { AlertTriangle, Inbox } from 'lucide-react';

export function Spinner({ size = 'md', label }) {
  return (
    <span className={`ui-spinner ui-spinner--${size}`} role="status" aria-live="polite">
      <span className="ui-spinner__circle" aria-hidden="true" />
      {label ? <span className="ui-spinner__label">{label}</span> : <span className="visually-hidden">Загрузка</span>}
    </span>
  );
}

export function Button({
  variant = 'primary',
  size = 'md',
  block = false,
  loading = false,
  disabled = false,
  icon = null,
  children,
  className = '',
  type = 'button',
  ...rest
}) {
  const classes = [
    'ui-btn',
    `ui-btn--${variant}`,
    `ui-btn--${size}`,
    block ? 'ui-btn--block' : '',
    loading ? 'is-loading' : '',
    className
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <span className="ui-btn__spinner" aria-hidden="true" /> : icon ? <span className="ui-btn__icon">{icon}</span> : null}
      <span className="ui-btn__label">{children}</span>
    </button>
  );
}

export function Card({ as: Tag = 'div', className = '', padded = true, children, ...rest }) {
  return (
    <Tag className={`ui-card ${padded ? 'ui-card--padded' : ''} ${className}`} {...rest}>
      {children}
    </Tag>
  );
}

export function Badge({ tone = 'neutral', children, title }) {
  return (
    <span className={`ui-badge ui-badge--${tone}`} title={title}>
      {children}
    </span>
  );
}

export function ProgressBar({ value = 0, max = 100, tone = 'primary', label, showValue = false }) {
  const percent = Math.max(0, Math.min(100, max ? (value / max) * 100 : 0));
  return (
    <div className="ui-progress">
      {label || showValue ? (
        <div className="ui-progress__meta">
          {label ? <span>{label}</span> : <span />}
          {showValue ? <span className="tabular">{value}/{max}</span> : null}
        </div>
      ) : null}
      <div
        className="ui-progress__track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={max}
        aria-valuenow={value}
        aria-label={typeof label === 'string' ? label : undefined}
      >
        <div className={`ui-progress__fill ui-progress__fill--${tone}`} style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export function Skeleton({ height = 16, width = '100%', radius = 8 }) {
  return <span className="ui-skeleton" style={{ height, width, borderRadius: radius }} aria-hidden="true" />;
}

/**
 * Единое состояние экрана/блока: загрузка, ошибка (с «Повторить») или пусто.
 */
export function StateView({ state, title, message, onRetry, action, compact = false }) {
  if (state === 'loading') {
    return (
      <div className={`ui-state ${compact ? 'ui-state--compact' : ''}`}>
        <Spinner label={message ?? 'Загрузка…'} />
      </div>
    );
  }
  const Icon = state === 'error' ? AlertTriangle : Inbox;
  return (
    <div className={`ui-state ui-state--${state} ${compact ? 'ui-state--compact' : ''}`} role={state === 'error' ? 'alert' : undefined}>
      <div className="ui-state__icon" aria-hidden="true"><Icon size={24} /></div>
      {title ? <div className="ui-state__title">{title}</div> : null}
      {message ? <div className="ui-state__message">{message}</div> : null}
      {state === 'error' && onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry}>
          Повторить
        </Button>
      ) : null}
      {action}
    </div>
  );
}
