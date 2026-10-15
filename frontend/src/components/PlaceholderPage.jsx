import React from 'react';
import { Construction } from 'lucide-react';

export function PlaceholderPage({ title, description, phase }) {
  return (
    <div className="page-container placeholder-page">
      <div className="placeholder-card">
        <div className="placeholder-icon-wrap">
          <Construction size={32} className="placeholder-icon" />
        </div>
        <h2 className="placeholder-title">{title}</h2>
        <p className="placeholder-desc">{description}</p>
        <span className="placeholder-phase-tag">{phase}</span>
        <p className="placeholder-note">
          Module architecture is staged. Implementation will begin in the scheduled phase.
        </p>
      </div>
    </div>
  );
}
