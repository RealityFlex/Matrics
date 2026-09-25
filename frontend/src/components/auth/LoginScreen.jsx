import React, { useState } from 'react';
import { Button } from '../ui/index.jsx';

/**
 * Вход в веб-версии (вне MAX). В мини-приложении MAX вход выполняется автоматически
 * по подписанным данным запуска, и этот экран не показывается.
 */
export function LoginScreen({ onLogin, isLoading, error }) {
  const [username, setUsername] = useState('');

  const handleSubmit = (event) => {
    event.preventDefault();
    if (!username.trim() || isLoading) {
      return;
    }
    onLogin(username.trim());
  };

  return (
    <div id="loginScreen" className="screen active">
      <div className="login-container">
        <div className="logo-container">
          <div className="logo-mark" aria-hidden="true">М</div>
          <h1 className="logo-title">Матрикс</h1>
          <p className="logo-subtitle">Персонаж растёт, когда ты ходишь на пары и учишься</p>
        </div>
        <form className="login-form" onSubmit={handleSubmit}>
          <label className="visually-hidden" htmlFor="usernameInput">
            Ник
          </label>
          <input
            type="text"
            id="usernameInput"
            placeholder="Введите ваш ник"
            maxLength={40}
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            disabled={isLoading}
            autoComplete="username"
          />
          <Button type="submit" size="lg" block loading={isLoading} disabled={!username.trim()}>
            Войти
          </Button>
          <p className="login-hint">
            Веб-версия для проверки. В MAX вход происходит автоматически. Для демо используйте ник <b>demo_student</b>.
          </p>
          {error ? (
            <p className="inline-error" role="alert">
              {error}
            </p>
          ) : null}
        </form>
      </div>
    </div>
  );
}
