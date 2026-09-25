import React, { useCallback, useEffect, useState } from 'react';
import { listEvents, listLessons } from '../../services/events.js';
import { EventsList } from './components/EventsList.jsx';
import { EventCard } from './components/EventCard.jsx';
import { useAppState } from '../../state/AppProvider.jsx';
import { BookOpen, CalendarDays } from 'lucide-react';
import { StateView } from '../../components/ui/index.jsx';

export function EventsSection({ isActive }) {
  const { user } = useAppState();
  const [events, setEvents] = useState([]);
  const [lessons, setLessons] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadEvents = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [eventsData, lessonsData] = await Promise.all([
        listEvents({ upcomingOnly: true, userId: user?.id }),
        user?.id ? listLessons({ userId: user.id }) : Promise.resolve([])
      ]);
      setEvents(Array.isArray(eventsData) ? eventsData : []);
      setLessons(Array.isArray(lessonsData) ? lessonsData : []);
    } catch (loadError) {
      console.error('Ошибка загрузки событий и занятий:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить события и занятия');
    } finally {
      setIsLoading(false);
    }
  }, [user?.id]);

  const handleEventUpdate = useCallback(() => {
    loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    if (isActive) {
      loadEvents();
    }
  }, [isActive, user?.id]); // Убрали loadEvents из зависимостей, добавили user?.id

  // Подготавливаем данные для отображения
  const lessonsWithType = lessons.map(lesson => ({ ...lesson, type: 'lesson' }))
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  
  const eventsWithType = events.map(event => ({ ...event, type: 'event' }))
    .sort((a, b) => new Date(a.start_time) - new Date(b.start_time));

  const renderList = (items, { idPrefix, listId, loadingText, errorTitle, emptyTitle }) => {
    if (isLoading) return <StateView state="loading" message={loadingText} compact />;
    if (error) return <StateView state="error" title={errorTitle} message={error} onRetry={loadEvents} compact />;
    if (!items.length) return <StateView state="empty" title={emptyTitle} compact />;
    return (
      <div className="cards-list" id={listId}>
        {items.map((item) => (
          <EventCard key={`${idPrefix}-${item.id}`} event={item} onUpdate={handleEventUpdate} />
        ))}
      </div>
    );
  };

  return (
    <div className="events-screen">
      {/* Блок занятий */}
      <div className="events-screen__block">
        <div className="section-header">
          <h2 className="inline-icon">
            <BookOpen size={22} aria-hidden="true" /> Занятия
          </h2>
        </div>
        {renderList(lessonsWithType, {
          idPrefix: 'lesson',
          listId: 'lessonsList',
          loadingText: 'Загружаем занятия…',
          errorTitle: 'Не удалось загрузить занятия',
          emptyTitle: 'Занятий нет'
        })}
      </div>

      {/* Блок событий */}
      <div className="events-screen__block">
        <div className="section-header">
          <h2 className="inline-icon">
            <CalendarDays size={22} aria-hidden="true" /> События
          </h2>
        </div>
        {renderList(eventsWithType, {
          idPrefix: 'event',
          listId: 'eventsList',
          loadingText: 'Загружаем события…',
          errorTitle: 'Не удалось загрузить события',
          emptyTitle: 'Событий нет'
        })}
      </div>
    </div>
  );
}
