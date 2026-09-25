import React, { useMemo } from 'react';
import { useAppDispatch, useAppState } from '../../state/AppProvider.jsx';
import { Modal } from '../common/Modal.jsx';
import { AppHeader } from './AppHeader.jsx';
import { DailyRewardMenuItem } from './DailyRewardMenuItem.jsx';
import { Ellipsis } from 'lucide-react';

// Статичная навигация - первые 4 секции + кнопка "Еще"
function BottomNav({
  navItems,
  activeSection,
  onChangeSection,
  onOpenMore,
  hasMore,
  badges,
  hasMoreBadge
}) {
  return (
    <nav className="bottom-nav">
      {navItems.map((item) => {
        const isActive = activeSection === item.id;
        const hasBadge = Boolean(badges?.[item.id]);
        return (
          <button
            key={item.id}
            className={`nav-item ${isActive ? 'active' : ''}`}
            data-section={item.id}
            type="button"
            onClick={() => onChangeSection(item.id)}
          >
            {hasBadge ? <span className="badge-dot" aria-hidden="true" /> : null}
            <span className="nav-icon">{item.icon}</span>
            <span className="nav-label">{item.label}</span>
          </button>
        );
      })}
      {hasMore ? (
        <button className="nav-item" data-section="more" type="button" onClick={onOpenMore}>
          {hasMoreBadge ? <span className="badge-dot" aria-hidden="true" /> : null}
          <span className="nav-icon">
            <Ellipsis size={22} strokeWidth={2} aria-hidden="true" />
          </span>
          <span className="nav-label">Ещё</span>
        </button>
      ) : null}
    </nav>
  );
}

export function AppLayout({ sections, onLogout }) {
  const { activeSection, modals, badges } = useAppState();
  const dispatch = useAppDispatch();

  // Первые 4 секции в основной навигации, остальные в модальном окне
  const primarySections = sections.slice(0, 4);
  const extraSections = sections.slice(4);
  const hasMoreSections = extraSections.length > 0;
  const hasMoreBadge =
    hasMoreSections && (extraSections.some((section) => badges?.[section.id]) || badges?.dailyReward);

  const activeSectionComponent = useMemo(
    () => sections.find((section) => section.id === activeSection) ?? sections[0],
    [sections, activeSection]
  );

  const handleChangeSection = (sectionId) => {
    dispatch({ type: 'SET_ACTIVE_SECTION', section: sectionId });
    dispatch({ type: 'CLEAR_BADGE', key: sectionId });
    // Закрываем модальное окно при выборе секции
    if (modals?.more) {
      dispatch({ type: 'TOGGLE_MODAL', modal: 'more', value: false });
    }
  };

  const handleOpenMore = () => {
    dispatch({ type: 'TOGGLE_MODAL', modal: 'more', value: true });
  };

  const handleCloseMore = () => {
    dispatch({ type: 'TOGGLE_MODAL', modal: 'more', value: false });
  };

  return (
    <div id="appScreen" className="screen active">
      <AppHeader onLogout={onLogout} />
      <main className="app-content">
        {sections.map((section) => {
          const SectionComponent = section.component;
          const isActive = activeSection === section.id;
          return (
            <section
              key={section.id}
              id={section.domId}
              className={`content-section ${isActive ? 'active' : ''}`}
              role="tabpanel"
              aria-hidden={!isActive}
            >
              <SectionComponent isActive={isActive} />
            </section>
          );
        })}
      </main>
      <BottomNav
        navItems={primarySections}
        activeSection={activeSectionComponent.id}
        onChangeSection={handleChangeSection}
        onOpenMore={handleOpenMore}
        hasMore={hasMoreSections}
        badges={badges}
        hasMoreBadge={hasMoreBadge}
      />
      {hasMoreSections ? (
        <Modal isOpen={modals?.more} onClose={handleCloseMore} title="Дополнительно">
          {extraSections.map((section) => (
            <button
              key={section.id}
              type="button"
              className="menu-item"
              data-section={section.id}
              onClick={() => handleChangeSection(section.id)}
            >
              {badges?.[section.id] ? <span className="badge-dot badge-dot--menu" aria-hidden="true" /> : null}
              <span className="menu-icon">{section.icon}</span>
              <span className="menu-label">{section.label}</span>
            </button>
          ))}
          <DailyRewardMenuItem onSelect={handleCloseMore} />
        </Modal>
      ) : null}
    </div>
  );
}

