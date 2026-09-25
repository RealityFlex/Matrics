import React from 'react';
import { ChallengeCard } from './ChallengeCard.jsx';
import { StateView } from '../../../components/ui/index.jsx';

export function ChallengesList({
  challenges,
  isLoading,
  error,
  currentUserId,
  onAccept,
  onDecline,
  processingChallengeId
}) {
  if (isLoading) {
    return (
      <div className="cards-list" id="challengesList">
        <StateView state="loading" message="Загружаем челленджи…" compact />
      </div>
    );
  }

  if (error) {
    return (
      <div className="cards-list" id="challengesList">
        <StateView state="error" title="Не удалось загрузить челленджи" message={error} compact />
      </div>
    );
  }

  if (!challenges.length) {
    return (
      <div className="cards-list" id="challengesList">
        <StateView state="empty" title="У вас пока нет челленджей" compact />
      </div>
    );
  }

  return (
    <div className="cards-list" id="challengesList">
      {challenges.map((challenge) => (
        <ChallengeCard
          key={challenge.id}
          challenge={challenge}
          currentUserId={currentUserId}
          onAccept={onAccept}
          onDecline={onDecline}
          isProcessing={processingChallengeId === challenge.id}
        />
      ))}
    </div>
  );
}

