import React from 'react';
import '../../../styles/features-extra.css';

export function StatsSummaryCard({ title, value, subtitle, icon }) {
  return (
    <div className="stat-card stats-tile">
      <div className="stats-tile__head">
        {icon ? <span className="stats-tile__icon">{icon}</span> : null}
        <span className="stats-tile__title">{title}</span>
      </div>
      <div className="stat-card-value stats-tile__value tabular">{value}</div>
      {subtitle ? <div className="stat-card-label stats-tile__hint">{subtitle}</div> : null}
    </div>
  );
}
