import React from 'react';
import { EventCard } from './EventCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function EventsList({ events, isLoading, error, onUpdate }) {
  if (isLoading) {
    return (
      <div className="cards-list" id="eventsList">
        <StateView state="loading" message="Загружаем события…" compact />
      </div>
    );
  }

  if (error) {
    return (
      <div className="cards-list" id="eventsList">
        <StateView state="error" title="Не удалось загрузить события" message={error} compact />
      </div>
    );
  }

  if (!events.length) {
    return (
      <div className="cards-list" id="eventsList">
        <StateView state="empty" title="Событий нет" compact />
      </div>
    );
  }

  return (
    <div className="cards-list" id="eventsList">
      {events.map((event) => (
        <EventCard key={event.id} event={event} onUpdate={onUpdate} />
      ))}
    </div>
  );
}

