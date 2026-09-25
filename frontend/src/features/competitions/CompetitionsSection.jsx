import React, { useCallback, useEffect, useState } from 'react';
import { useAppState } from '../../state/AppProvider.jsx';
import {
  listCompetitions,
  listUserChallenges,
  acceptChallenge,
  declineChallenge
} from '../../services/competitions.js';
import { ChallengeCreateModal } from './components/ChallengeCreateModal.jsx';
import { CompetitionsList } from './components/CompetitionsList.jsx';
import { ChallengesList } from './components/ChallengesList.jsx';
import { Flag, Plus } from 'lucide-react';
import { Button } from '../../components/ui/index.jsx';

export function CompetitionsSection({ isActive }) {
  const { user } = useAppState();

  const [competitions, setCompetitions] = useState([]);
  const [competitionsError, setCompetitionsError] = useState(null);
  const [isLoadingCompetitions, setIsLoadingCompetitions] = useState(false);

  const [challenges, setChallenges] = useState([]);
  const [challengesError, setChallengesError] = useState(null);
  const [isLoadingChallenges, setIsLoadingChallenges] = useState(false);
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [processingChallengeId, setProcessingChallengeId] = useState(null);

  const loadCompetitions = useCallback(async () => {
    setIsLoadingCompetitions(true);
    setCompetitionsError(null);
    try {
      const data = await listCompetitions({ activeOnly: true, userId: user?.id || null });
      setCompetitions(Array.isArray(data) ? data : []);
    } catch (error) {
      console.error('Ошибка загрузки соревнований:', error);
      setCompetitionsError(error.message ?? 'Не удалось загрузить соревнования');
    } finally {
      setIsLoadingCompetitions(false);
    }
  }, [user?.id]);

  const loadChallenges = useCallback(async () => {
    if (!user?.id) {
      setChallenges([]);
      return;
    }
    setIsLoadingChallenges(true);
    setChallengesError(null);
    try {
      const data = await listUserChallenges(user.id);
      // Фильтруем отклонённые челленджи
      const filteredChallenges = Array.isArray(data) 
        ? data.filter(challenge => challenge.status !== 'declined')
        : [];
      setChallenges(filteredChallenges);
    } catch (error) {
      console.error('Ошибка загрузки челленджей:', error);
      setChallengesError(error.message ?? 'Не удалось загрузить челленджи');
    } finally {
      setIsLoadingChallenges(false);
    }
  }, [user?.id]);

  const handleChallengeAction = useCallback(
    async (challengeId, action) => {
      if (!user?.id) {
        return;
      }
      setProcessingChallengeId(challengeId);
      setChallengesError(null);
      try {
        if (action === 'accept') {
          await acceptChallenge(challengeId, user.id);
        } else {
          await declineChallenge(challengeId, user.id);
        }
        await loadChallenges();
      } catch (error) {
        console.error('Ошибка обработки челленджа:', error);
        setChallengesError(error.message ?? 'Не удалось обновить челлендж');
      } finally {
        setProcessingChallengeId(null);
      }
    },
    [user?.id, loadChallenges]
  );

  useEffect(() => {
    if (isActive) {
      loadCompetitions();
      if (user?.id) {
        loadChallenges();
      }
    }
  }, [isActive, user?.id]); // Убрали loadCompetitions и loadChallenges из зависимостей

  return (
    <div className="comp-screen">
      <div className="section-header">
        <h2 className="inline-icon">
          <Flag size={22} aria-hidden="true" /> Соревнования
        </h2>
      </div>

      <h3 className="section-subtitle">Глобальные соревнования</h3>
      <CompetitionsList
        competitions={competitions}
        isLoading={isLoadingCompetitions}
        error={competitionsError}
        onUpdate={loadCompetitions}
      />

      <div className="section-header comp-screen__subheader">
        <h3 className="section-subtitle">Мои челленджи</h3>
        <Button size="sm" variant="secondary" icon={<Plus size={16} aria-hidden="true" />} onClick={() => setIsCreateModalOpen(true)} disabled={!user}>
          Создать
        </Button>
      </div>
      <ChallengesList
        challenges={challenges}
        isLoading={isLoadingChallenges}
        error={challengesError}
        currentUserId={user?.id}
        onAccept={(challengeId) => handleChallengeAction(challengeId, 'accept')}
        onDecline={(challengeId) => handleChallengeAction(challengeId, 'decline')}
        processingChallengeId={processingChallengeId}
      />
      <ChallengeCreateModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        currentUser={user}
        onCreated={() => {
          loadChallenges();
        }}
      />
    </div>
  );
}

