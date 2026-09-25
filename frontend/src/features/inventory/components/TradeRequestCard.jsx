import React from 'react';
import { ArrowDownLeft, ArrowUpRight, Ban, Calendar, Check, Gift, X } from 'lucide-react';
import { getItemIcon, getItemImageSrc } from '../../../utils/itemPresentation.js';
import { Badge, Button } from '../../../components/ui/index.jsx';

const STATUS_INFO = {
  pending: { label: 'Ожидает ответа', tone: 'warning' },
  accepted: { label: 'Принят', tone: 'success' },
  rejected: { label: 'Отклонён', tone: 'danger' },
  cancelled: { label: 'Отменён', tone: 'neutral' }
};

function TradeItem({ item, itemId, quantity }) {
  const imageSrc = item ? getItemImageSrc(item) : null;
  const name = item?.name || `Предмет #${itemId}`;
  return (
    <span className="trade-item">
      {imageSrc ? (
        <img src={imageSrc} alt="" className="trade-item__image" />
      ) : (
        <span className="trade-item__icon">{getItemIcon(item?.type || 'special', itemId, 16)}</span>
      )}
      <strong>{name}</strong>
      <span className="tabular">×{quantity}</span>
    </span>
  );
}

export function TradeRequestCard({
  tradeRequest,
  currentUserId,
  onAccept,
  onReject,
  onCancel,
  isProcessing
}) {
  const isIncoming = tradeRequest.recipient_id === currentUserId;

  const hasInitiatorItem = tradeRequest.initiator_item_id != null;
  const hasRequestedItem = tradeRequest.requested_item_id != null;
  const isGift = !hasRequestedItem;

  const statusInfo = STATUS_INFO[tradeRequest.status] ?? { label: 'Неизвестный статус', tone: 'neutral' };
  const DirectionIcon = isIncoming ? ArrowDownLeft : ArrowUpRight;

  return (
    <div className="card fc-card">
      <div className="fc-card__head">
        <div className="fc-card__title inline-icon">
          <DirectionIcon size={18} aria-hidden="true" className="icon-muted" />
          {isIncoming ? 'Входящий обмен' : 'Исходящий обмен'}
        </div>
        <Badge tone={statusInfo.tone}>{statusInfo.label}</Badge>
      </div>
      <div className="fc-rows">
        <div className="fc-row">
          <span>От:</span>
          <strong>{tradeRequest.initiator_username || `Пользователь #${tradeRequest.initiator_id}`}</strong>
        </div>
        <div className="fc-row">
          <span>Кому:</span>
          <strong>{tradeRequest.recipient_username || `Пользователь #${tradeRequest.recipient_id}`}</strong>
        </div>
        {hasInitiatorItem && (
          <div className="fc-row trade-row">
            <span>Предлагается:</span>
            <TradeItem
              item={tradeRequest.initiator_item}
              itemId={tradeRequest.initiator_item_id}
              quantity={tradeRequest.initiator_quantity}
            />
          </div>
        )}
        {hasRequestedItem && (
          <div className="fc-row trade-row">
            <span>Взамен:</span>
            <TradeItem
              item={tradeRequest.requested_item}
              itemId={tradeRequest.requested_item_id}
              quantity={tradeRequest.requested_quantity}
            />
          </div>
        )}
        {isGift && (
          <div className="fc-row">
            <Gift size={16} aria-hidden="true" className="icon-success" />
            <span>Подарок — ничего не требуется взамен</span>
          </div>
        )}
      </div>
      {tradeRequest.comment && (
        <div className="fc-note">
          <span className="fc-note__label">Комментарий</span>
          {tradeRequest.comment}
        </div>
      )}
      {tradeRequest.created_at && (
        <div className="fc-meta">
          <span className="fc-chip">
            <Calendar size={14} aria-hidden="true" />
            {new Date(tradeRequest.created_at).toLocaleString('ru-RU', {
              day: 'numeric',
              month: 'short',
              hour: '2-digit',
              minute: '2-digit'
            })}
          </span>
        </div>
      )}
      {tradeRequest.status === 'pending' && (
        <div className="fc-actions">
          {isIncoming ? (
            <div className="fc-actions__row">
              <Button
                size="sm"
                variant="secondary"
                icon={<X size={16} />}
                onClick={() => onReject(tradeRequest.id)}
                disabled={isProcessing}
              >
                Отклонить
              </Button>
              <Button
                size="sm"
                icon={<Check size={16} />}
                onClick={() => onAccept(tradeRequest.id)}
                loading={isProcessing}
              >
                Принять
              </Button>
            </div>
          ) : (
            onCancel && (
              <Button
                size="sm"
                variant="secondary"
                block
                icon={<Ban size={16} />}
                onClick={() => onCancel(tradeRequest.id)}
                loading={isProcessing}
              >
                Отменить предложение
              </Button>
            )
          )}
        </div>
      )}
    </div>
  );
}
