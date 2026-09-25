import React from 'react';
import { CompetitionCard } from './CompetitionCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function CompetitionsList({ competitions, isLoading, error, onUpdate }) {
  if (isLoading) {
    return (
      <div className="cards-list" id="competitionsList">
        <StateView state="loading" message="Загружаем соревнования…" compact />
      </div>
    );
  }

  if (error) {
    return (
      <div className="cards-list" id="competitionsList">
        <StateView state="error" title="Не удалось загрузить соревнования" message={error} compact />
      </div>
    );
  }

  if (!competitions.length) {
    return (
      <div className="cards-list" id="competitionsList">
        <StateView state="empty" title="Соревнований пока нет" compact />
      </div>
    );
  }

  return (
    <div className="cards-list" id="competitionsList">
      {competitions.map((competition) => (
        <CompetitionCard key={competition.id} competition={competition} onUpdate={onUpdate} />
      ))}
    </div>
  );
}

