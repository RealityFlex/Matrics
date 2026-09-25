import React, { useCallback, useEffect, useState } from 'react';
import { FileDown } from 'lucide-react';
import { adminApi } from '../api.js';
import { UserDetailsModal } from '../components/UserDetailsModal.jsx';
import { exportAllUsersToPDF } from '../utils/pdfExport.js';
import { NotificationModal } from '../../components/common/NotificationModal.jsx';
import { ConfirmModal } from '../../components/common/ConfirmModal.jsx';
import { Button, StateView } from '../../components/ui/index.jsx';
import { StatValue } from '../../components/ui/icons.jsx';
import { ROLE_LABELS, labelFor } from '../labels.js';

export function UsersSection({ isActive }) {
  const [users, setUsers] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [selectedUserId, setSelectedUserId] = useState(null);
  const [isExportingAll, setIsExportingAll] = useState(false);
  const [notification, setNotification] = useState({ isOpen: false, message: '', type: 'info', title: '' });
  const [exportConfirm, setExportConfirm] = useState({ isOpen: false, userCount: 0 });

  const loadUsers = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await adminApi.listUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (loadError) {
      console.error('Ошибка загрузки пользователей:', loadError);
      setError(loadError.message ?? 'Не удалось загрузить пользователей');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isActive) {
      loadUsers();
    }
  }, [isActive, loadUsers]);

  const handleExportAllUsers = () => {
    if (!users.length) {
      setNotification({
        isOpen: true,
        message: 'Нет пользователей для экспорта',
        type: 'warning',
        title: 'Предупреждение'
      });
      return;
    }

    setExportConfirm({ isOpen: true, userCount: users.length });
  };

  const handleExportConfirm = async () => {
    setIsExportingAll(true);
    setExportConfirm({ isOpen: false, userCount: 0 });
    try {
      await exportAllUsersToPDF(users, adminApi);
      setNotification({
        isOpen: true,
        message: `Экспорт завершён! Создано ${users.length} PDF файлов.`,
        type: 'success',
        title: 'Успешно'
      });
    } catch (error) {
      console.error('Ошибка массового экспорта:', error);
      setNotification({
        isOpen: true,
        message: `Ошибка при экспорте: ${error.message}`,
        type: 'error',
        title: 'Ошибка'
      });
    } finally {
      setIsExportingAll(false);
    }
  };

  return (
    <section id="users-section" className={`admin-section ${isActive ? 'active' : ''}`}>
      <div className="section-header">
        <h2>Управление пользователями</h2>
        {users.length > 0 && (
          <Button
            size="sm"
            icon={<FileDown size={16} aria-hidden="true" />}
            onClick={handleExportAllUsers}
            loading={isExportingAll}
            disabled={isLoading}
          >
            {isExportingAll ? 'Экспорт…' : 'Экспорт всех в PDF'}
          </Button>
        )}
      </div>
      <div className="table-container">
        {isLoading ? (
          <StateView state="loading" message="Загрузка пользователей…" />
        ) : error ? (
          <StateView state="error" title="Не удалось загрузить пользователей" message={error} onRetry={loadUsers} />
        ) : !users.length ? (
          <StateView state="empty" title="Пользователей пока нет" />
        ) : (
          <table>
            <thead>
              <tr>
                <th>ID</th>
                <th>Имя пользователя</th>
                <th>Эл. почта</th>
                <th>Роль</th>
                <th>Монеты</th>
                <th>Действия</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.id}</td>
                  <td>{user.username}</td>
                  <td>{user.email}</td>
                  <td>{labelFor(ROLE_LABELS, user.role ?? 'student', 'Другая роль')}</td>
                  <td>
                    <span className="admin-inline">
                      <StatValue kind="coins" value={user.coins ?? 0} />
                    </span>
                  </td>
                  <td>
                    <Button size="sm" variant="secondary" onClick={() => setSelectedUserId(user.id)}>
                      Подробнее
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      <UserDetailsModal
        isOpen={selectedUserId !== null}
        onClose={() => setSelectedUserId(null)}
        userId={selectedUserId}
      />
      <NotificationModal
        isOpen={notification.isOpen}
        onClose={() => setNotification({ ...notification, isOpen: false })}
        title={notification.title}
        message={notification.message}
        type={notification.type}
      />
      <ConfirmModal
        isOpen={exportConfirm.isOpen}
        onClose={() => setExportConfirm({ isOpen: false, userCount: 0 })}
        onConfirm={handleExportConfirm}
        title="Экспорт пользователей"
        message={`Экспортировать статистику для всех ${exportConfirm.userCount} пользователей? Это может занять некоторое время.`}
        confirmText="Экспортировать"
        cancelText="Отмена"
        type="warning"
      />
    </section>
  );
}


