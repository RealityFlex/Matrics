import React, { useState, useEffect, useRef } from 'react';
import { openLootbox } from '../../../services/lootbox.js';
import { getRarityColor, getRarityLabel, getItemImageSrc, getItemIcon } from '../../../utils/itemPresentation.js';
import { Gift } from 'lucide-react';
import { Button } from '../../../components/ui/index.jsx';
import { RewardChips } from '../../../components/ui/icons.jsx';
import '../../../styles/lootbox.css';

// Маппинг русских названий на английские ключи
const RARITY_MAP = {
  'Обычный': 'common',
  'Необычный': 'uncommon',
  'Редкий': 'rare',
  'Эпический': 'epic',
  'Легендарный': 'legendary'
};

// Обратный маппинг для получения русского названия по английскому ключу
const RARITY_REVERSE_MAP = {
  'common': 'Обычный',
  'uncommon': 'Необычный',
  'rare': 'Редкий',
  'epic': 'Эпический',
  'legendary': 'Легендарный'
};

const RARITIES_RU = ['Обычный', 'Необычный', 'Редкий', 'Эпический', 'Легендарный'];

const ANIMATION_PHASES = {
  FAST: 'fast',      // Быстрая смена карточек
  SLOWING: 'slowing', // Замедление
  STOPPING: 'stopping', // Остановка
  RESULT: 'result'    // Показ результата
};

export function LootboxModal({ isOpen, onClose, userId, onResult, onOpenAnother }) {
  const [phase, setPhase] = useState(ANIMATION_PHASES.FAST);
  const [currentRarity, setCurrentRarity] = useState(RARITIES_RU[0]);
  const [resultItem, setResultItem] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);
  const timeoutRef = useRef(null);
  const audioContextRef = useRef(null);
  const soundSourcesRef = useRef([]);

  // Инициализация AudioContext
  useEffect(() => {
    if (typeof window !== 'undefined' && window.AudioContext) {
      try {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      } catch (e) {
        console.warn('AudioContext не поддерживается:', e);
      }
    }

    return () => {
      // Очистка при размонтировании
      if (audioContextRef.current) {
        audioContextRef.current.close().catch(() => {});
      }
    };
  }, []);

  // Воспроизведение звука прокрутки
  const playScrollSound = () => {
    if (!audioContextRef.current) {
      return;
    }

    try {
      const audioContext = audioContextRef.current;
      
      // Активируем AudioContext если он в suspended состоянии (требуется для браузеров)
      if (audioContext.state === 'suspended') {
        audioContext.resume().catch(() => {});
      }
      
      // Создаем осциллятор для звука
      const oscillator = audioContext.createOscillator();
      const gainNode = audioContext.createGain();
      
      // Настраиваем звук (короткий высокий звук)
      oscillator.type = 'sine';
      oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
      oscillator.frequency.exponentialRampToValueAtTime(400, audioContext.currentTime + 0.05);
      
      // Настраиваем громкость (быстрое затухание)
      gainNode.gain.setValueAtTime(0.1, audioContext.currentTime);
      gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.05);
      
      // Подключаем
      oscillator.connect(gainNode);
      gainNode.connect(audioContext.destination);
      
      // Воспроизводим
      oscillator.start(audioContext.currentTime);
      oscillator.stop(audioContext.currentTime + 0.05);
      
      // Сохраняем источник для возможной очистки
      soundSourcesRef.current.push({ oscillator, gainNode });
      
      // Очищаем старые источники (оставляем только последние 10)
      if (soundSourcesRef.current.length > 10) {
        const old = soundSourcesRef.current.shift();
        try {
          old.oscillator.stop();
          old.oscillator.disconnect();
          old.gainNode.disconnect();
        } catch (e) {
          // Игнорируем ошибки при очистке
        }
      }
    } catch (e) {
      // Игнорируем ошибки воспроизведения звука
      console.warn('Ошибка воспроизведения звука:', e);
    }
  };

  useEffect(() => {
    if (isOpen) {
      startAnimation();
    } else {
      cleanup();
      resetState();
    }

    return () => {
      cleanup();
    };
  }, [isOpen]);

  const resetState = () => {
    setPhase(ANIMATION_PHASES.FAST);
    setCurrentRarity(RARITIES_RU[0]);
    setResultItem(null);
    setError(null);
    setIsLoading(false);
  };

  const cleanup = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  const startAnimation = async () => {
    resetState();
    setIsLoading(true);
    setError(null);

    try {
      // Открываем лутбокс через API
      const result = await openLootbox(userId);
      
      if (!result || !result.item) {
        throw new Error('Не удалось открыть лутбокс');
      }

      const item = result.item;
      const targetRarityEn = item.rarity || 'common';
      const targetRarityRu = RARITY_REVERSE_MAP[targetRarityEn] || 'Обычный';

      // Фаза 1: Быстрая смена карточек (1500ms) - замедлено
      setPhase(ANIMATION_PHASES.FAST);
      let cardIndex = 0;
      intervalRef.current = setInterval(() => {
        setCurrentRarity(RARITIES_RU[cardIndex % RARITIES_RU.length]);
        playScrollSound(); // Воспроизводим звук при каждой смене карточки
        cardIndex++;
      }, 200); // Увеличено с 50 до 200ms - теперь видно каждую карточку

      // Фаза 2: Замедление (2000ms) - замедлено
      timeoutRef.current = setTimeout(() => {
        cleanup();
        setPhase(ANIMATION_PHASES.SLOWING);
        
        let slowIndex = 0;
        const slowInterval = setInterval(() => {
          setCurrentRarity(RARITIES_RU[slowIndex % RARITIES_RU.length]);
          playScrollSound(); // Воспроизводим звук при каждой смене карточки
          slowIndex++;
        }, 300); // Увеличено с 150 до 300ms - более плавное замедление

        // Фаза 3: Остановка на нужной редкости (800ms)
        setTimeout(() => {
          clearInterval(slowInterval);
          setPhase(ANIMATION_PHASES.STOPPING);
          setCurrentRarity(targetRarityRu);

          // Фаза 4: Показ результата (1000ms)
          setTimeout(() => {
            setPhase(ANIMATION_PHASES.RESULT);
            setResultItem(item);
            setIsLoading(false);

            if (onResult) {
              onResult(result);
            }
          }, 800);
        }, 2000); // Увеличено с 1000 до 2000ms
      }, 1500); // Увеличено с 500 до 1500ms
    } catch (err) {
      cleanup();
      setIsLoading(false);
      setError(err.message || 'Ошибка при открытии лутбокса');
      console.error('Ошибка открытия лутбокса:', err);
    }
  };

  const handleClose = () => {
    if (phase === ANIMATION_PHASES.RESULT || error) {
      cleanup();
      resetState();
      onClose();
    }
  };

  if (!isOpen) {
    return null;
  }

  // Получаем английский ключ для цвета (если currentRarity - русское название)
  const rarityKey = RARITY_MAP[currentRarity] || currentRarity;
  const rarityColor = getRarityColor(rarityKey);
  const rarityLabel = currentRarity; // Используем русское название напрямую
  const showResult = phase === ANIMATION_PHASES.RESULT && resultItem;

  return (
    <div className="lootbox-modal-overlay" onClick={handleClose}>
      <div
        className="lootbox-modal-content"
        role="dialog"
        aria-modal="true"
        aria-label="Открытие лутбокса"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="lootbox-container">
          {error ? (
            <div className="lootbox-error" role="alert">
              <h3>Не удалось открыть лутбокс</h3>
              <p>{error}</p>
              <Button onClick={handleClose}>Закрыть</Button>
            </div>
          ) : showResult ? (
            <div className="lootbox-result">
              <div className="lootbox-result-header">
                <h2>Поздравляем!</h2>
                <p>Вы получили:</p>
              </div>
              <div className="lootbox-result-card" style={{ '--rarity': getRarityColor(resultItem.rarity) }}>
                {getItemImageSrc(resultItem) ? (
                  <img
                    src={getItemImageSrc(resultItem)}
                    alt={resultItem.name}
                    className="lootbox-result-image"
                  />
                ) : (
                  <div className="lootbox-result-icon">
                    {getItemIcon(resultItem.type, resultItem.id, 96)}
                  </div>
                )}
                <div className="lootbox-result-name">{resultItem.name}</div>
                <span className="item-rarity">{getRarityLabel(resultItem.rarity)}</span>
                {(() => {
                  const rewards = {
                    coins: resultItem.reward_coins ?? resultItem.rewardCoins ?? 0,
                    intelligence: resultItem.reward_intelligence_points ?? resultItem.rewardIntelligencePoints ?? 0,
                    satisfaction: resultItem.reward_satisfaction ?? resultItem.rewardSatisfaction ?? 0
                  };
                  if (rewards.coins > 0 || rewards.intelligence > 0 || rewards.satisfaction > 0) {
                    return (
                      <div className="lootbox-result-rewards">
                        <div className="lootbox-result-rewards-title">При использовании</div>
                        <RewardChips rewards={rewards} />
                      </div>
                    );
                  }
                  return null;
                })()}
              </div>
              <div className="lootbox-result-buttons">
                <Button variant="secondary" onClick={handleClose}>
                  Отлично
                </Button>
                <Button
                  icon={<Gift size={16} />}
                  onClick={() => {
                    handleClose();
                    if (onOpenAnother) {
                      onOpenAnother();
                    }
                  }}
                >
                  Открыть ещё
                </Button>
              </div>
            </div>
          ) : (
            <div className="lootbox-animation" aria-live="polite">
              <div className="lootbox-card-container">
                <div
                  className={`lootbox-card ${phase === ANIMATION_PHASES.STOPPING ? 'stopping' : ''}`}
                  style={{ '--rarity': rarityColor }}
                >
                  <div className="lootbox-card-glow" />
                  <div className="lootbox-card-content">
                    <div className="lootbox-card-rarity">{rarityLabel}</div>
                    <div className="lootbox-card-question" aria-hidden="true">?</div>
                  </div>
                </div>
              </div>
              {phase === ANIMATION_PHASES.FAST && (
                <div className="lootbox-loading-text">Открываем лутбокс…</div>
              )}
              {phase === ANIMATION_PHASES.SLOWING && (
                <div className="lootbox-loading-text">Замедляем…</div>
              )}
              {phase === ANIMATION_PHASES.STOPPING && (
                <div className="lootbox-loading-text">Останавливаемся…</div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

