import React, { useEffect, useState } from 'react';
import { Modal } from '../../components/common/Modal.jsx';
import { Button, StateView } from '../../components/ui/index.jsx';
import { getAdminToken, setAdminToken } from '../../services/apiClient.js';
import { adminApi } from '../api.js';

/**
 * Вход в админ-панель по токену администратора (ADMIN_TOKEN на сервере).
 * Токен проверяется бэкендом и хранится только в sessionStorage вкладки —
 * пароли больше не зашиваются в сборку фронтенда.
 */
export function AdminAuth({ children }) {
  const [status, setStatus] = useState('checking'); // checking | login | ready
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (!getAdminToken()) {
      setStatus('login');
      return;
    }
    adminApi
      .verifyAdminToken()
      .then(() => setStatus('ready'))
      .catch(() => {
        setAdminToken('');
        setStatus('login');
      });
  }, []);

  const handleLogin = async (event) => {
    event.preventDefault();
    if (!token.trim()) {
      setError('Введите токен администратора');
      return;
    }
    setIsSubmitting(true);
    setError('');
    setAdminToken(token.trim());
    try {
      await adminApi.verifyAdminToken();
      setStatus('ready');
      setToken('');
    } catch (verifyError) {
      setAdminToken('');
      setError(verifyError?.status === 401 ? 'Неверный токен администратора' : verifyError?.message ?? 'Сервер недоступен');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleLogout = () => {
    setAdminToken('');
    setStatus('login');
  };

  if (status === 'checking') {
    return (
      <div className="admin-page admin-page--center">
        <StateView state="loading" message="Проверяем доступ…" />
      </div>
    );
  }

  if (status === 'login') {
    return (
      <div className="admin-page">
        <Modal isOpen onClose={null} title="Вход в админ-панель">
          <form onSubmit={handleLogin} className="admin-login">
            <p className="admin-login__hint">
              Введите токен администратора (переменная <code>ADMIN_TOKEN</code> в <code>.env</code> сервера). Для проверки жюри
              токен указан на первом слайде презентации.
            </p>
            <label htmlFor="admin-token" className="admin-login__label">
              Токен
            </label>
            <input
              id="admin-token"
              type="password"
              className="admin-login__input"
              value={token}
              onChange={(e) => setToken(e.target.value)}
              autoFocus
              autoComplete="current-password"
            />
            {error ? (
              <div className="inline-error" role="alert">
                {error}
              </div>
            ) : null}
            <Button type="submit" block loading={isSubmitting}>
              Войти
            </Button>
          </form>
        </Modal>
      </div>
    );
  }

  return (
    <>
      {children}
      <button type="button" className="admin-logout" onClick={handleLogout}>
        Выйти
      </button>
    </>
  );
}
