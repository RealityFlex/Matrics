import React, { useCallback, useEffect, useState } from 'react';
import { adminApi } from '../api.js';
import { Bot, Database } from 'lucide-react';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Badge, Button, StateView } from '../../components/ui/index.jsx';

export function SettingsSection({ isActive }) {
  const [isMaxBotEnabled, setIsMaxBotEnabled] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isResetting, setIsResetting] = useState(false);
  const [resetConfirm, setResetConfirm] = useState({ isOpen: false });
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const loadSettings = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const settings = await adminApi.getMaxBotSettings();
      setIsMaxBotEnabled(settings.enabled ?? false);
    } catch (loadError) {
      console.error('Ошибка загрузки настроек:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить настройки');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadSettings();
    }
  }, [isActive]); // Убрали loadSettings из зависимостей

  const handleToggleMaxBot = async () => {
    setIsSaving(true);
    setError(null);
    setSuccess(null);
    try {
      const newValue = !isMaxBotEnabled;
      await adminApi.updateMaxBotSettings({ enabled: newValue });
      setIsMaxBotEnabled(newValue);
      setSuccess(`Интеграция с MAX ${newValue ? 'включена' : 'выключена'}`);
      setTimeout(() => setSuccess(null), 3000);
    } catch (saveError) {
      console.error('Ошибка сохранения настроек:', saveError);
      setError(saveError.message ?? 'Не удалось сохранить настройки');
    } finally {
      setIsSaving(false);
    }
  };

  if (!isActive) return null;

  return (
    <section className="admin-section active settings-section">
      <div className="section-header">
        <h2>Настройки</h2>
      </div>

      {isLoading ? <StateView state="loading" message="Загрузка настроек…" compact /> : null}

      {error ? (
        <div className="inline-error" role="alert">
          {error}
        </div>
      ) : null}

      {success ? (
        <div className="admin-success" role="status">
          {success}
        </div>
      ) : null}

      <div className="admin-settings-card">
        <h3>
          <Bot size={20} aria-hidden="true" /> Интеграция с MAX
        </h3>
        <p>
          Управление ответами чат-бота MAX. Когда интеграция выключена, бот не будет отвечать на сообщения пользователей.
        </p>

        <div className="admin-inline">
          <label className="admin-toggle">
            <input
              type="checkbox"
              checked={isMaxBotEnabled}
              onChange={handleToggleMaxBot}
              disabled={isSaving || isLoading}
            />
            <Badge tone={isMaxBotEnabled ? 'success' : 'warning'}>{isMaxBotEnabled ? 'Включена' : 'Выключена'}</Badge>
          </label>
          {isSaving ? <span className="admin-muted">Сохранение…</span> : null}
        </div>

        <div className={`admin-status-box ${isMaxBotEnabled ? 'admin-status-box--on' : 'admin-status-box--off'}`}>
          <strong>Текущий статус:</strong>{' '}
          {isMaxBotEnabled
            ? 'Бот активно отвечает на сообщения пользователей'
            : 'Бот не отвечает на сообщения. Все запросы игнорируются.'}
        </div>
      </div>

      <div className="admin-settings-card admin-settings-card--danger">
        <h3>
          <Database size={20} aria-hidden="true" /> Управление базой данных
        </h3>
        <p>
          <span className="admin-danger-text">Опасно:</span> эта операция полностью удалит все данные из базы данных и
          создаст её заново с начальными данными (5 предметов и 1 достижение).
        </p>

        <Button variant="danger" loading={isResetting} onClick={() => setResetConfirm({ isOpen: true })}>
          {isResetting ? 'Снос базы данных…' : 'Снести базу данных'}
        </Button>
      </div>
      <ConfirmModal
        isOpen={resetConfirm.isOpen}
        onClose={() => setResetConfirm({ isOpen: false })}
        onConfirm={async () => {
          setResetConfirm({ isOpen: false });
          setIsResetting(true);
          setError(null);
          setSuccess(null);
          try {
            const result = await adminApi.resetDatabase();
            setSuccess(`База данных успешно снесена! Создано: ${result.created_items} предметов, ${result.created_achievements} достижений`);
            setTimeout(() => setSuccess(null), 10000);
          } catch (resetError) {
            console.error('Ошибка сноса базы данных:', resetError);
            setError(resetError.message ?? 'Не удалось снести базу данных');
          } finally {
            setIsResetting(false);
          }
        }}
        title="Внимание"
        message="Снести базу данных? Будут удалены все данные (пользователи, персонажи, задачи, предметы и т. д.), база будет создана заново с 5 предметами и 1 достижением. Действие необратимо."
        confirmText="Да, снести базу"
        cancelText="Отмена"
        type="danger"
      />
    </section>
  );
}

