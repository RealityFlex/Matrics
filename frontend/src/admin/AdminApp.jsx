import React, { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { ItemsSection } from './sections/ItemsSection.jsx';
import { EventsSection } from './sections/EventsSection.jsx';
import { AchievementsSection } from './sections/AchievementsSection.jsx';
import { ShopSection } from './sections/ShopSection.jsx';
import { UsersSection } from './sections/UsersSection.jsx';
import { StatsSection } from './sections/StatsSection.jsx';
import { SettingsSection } from './sections/SettingsSection.jsx';
import { CompetitionsSection } from './sections/CompetitionsSection.jsx';
import { AdminAuth } from './components/AdminAuth.jsx';
import { CuratorSection } from './sections/CuratorSection.jsx';
import { ScheduleImportSection } from './sections/ScheduleImportSection.jsx';
import { OnboardingSection } from './sections/OnboardingSection.jsx';
import { ArrowLeft, LayoutDashboard } from 'lucide-react';
import '../admin.css';
import '../styles/admin-extra.css';

export function AdminApp() {
  const sections = useMemo(
    () => [
      { id: 'curator', label: 'Куратор', Component: CuratorSection },
      { id: 'onboarding', label: 'Подключение вуза', Component: OnboardingSection },
      { id: 'events', label: 'Пары и события', Component: EventsSection },
      { id: 'schedule', label: 'Тестовое расписание', Component: ScheduleImportSection },
      { id: 'items', label: 'Предметы', Component: ItemsSection },
      { id: 'competitions', label: 'Соревнования', Component: CompetitionsSection },
      { id: 'achievements', label: 'Достижения', Component: AchievementsSection },
      { id: 'shop', label: 'Магазин', Component: ShopSection },
      { id: 'users', label: 'Пользователи', Component: UsersSection },
      { id: 'stats', label: 'Статистика', Component: StatsSection },
      { id: 'settings', label: 'Настройки', Component: SettingsSection }
    ],
    []
  );
  const [activeSection, setActiveSection] = useState(sections[0]?.id ?? 'curator');

  // Админка — светлая тема той же палитры (рабочий интерфейс для большого экрана)
  useEffect(() => {
    const root = document.documentElement;
    const previous = root.getAttribute('data-theme');
    root.setAttribute('data-theme', 'light');
    return () => {
      if (previous) root.setAttribute('data-theme', previous);
    };
  }, []);

  return (
    <AdminAuth>
      <div className="admin-page">
        <div className="admin-container">
          <header className="admin-header">
            <h1>
              <LayoutDashboard size={24} aria-hidden="true" /> Админ-панель
            </h1>
            <nav className="admin-nav">
              {sections.map((section) => (
                <button
                  key={section.id}
                  type="button"
                  className={`nav-btn ${activeSection === section.id ? 'active' : ''}`}
                  data-section={section.id}
                  aria-pressed={activeSection === section.id}
                  onClick={() => setActiveSection(section.id)}
                >
                  {section.label}
                </button>
              ))}
            </nav>
            <Link to="/" className="back-link">
              <ArrowLeft size={16} aria-hidden="true" /> Вернуться на сайт
            </Link>
          </header>
          <main className="admin-content">
            {sections.map(({ id, Component }) => (
              <Component key={id} isActive={activeSection === id} />
            ))}
          </main>
        </div>
      </div>
    </AdminAuth>
  );
}
