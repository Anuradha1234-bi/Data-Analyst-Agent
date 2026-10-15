import React from 'react';
import {
  LayoutDashboard,
  Database,
  Activity,
  Sparkles,
  AlertTriangle,
  TrendingUp,
  MessageSquareText,
  FileText,
  Shield,
} from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const navIcons = {
  dashboard: LayoutDashboard,
  datasets: Database,
  profiling: Activity,
  cleaning: Sparkles,
  anomalies: AlertTriangle,
  prediction: TrendingUp,
  'ask-analyst': MessageSquareText,
  reports: FileText,
  'admin-users': Shield,
};

export function Sidebar({ items, activeItem, onSelect }) {
  const { user, isAdmin, isAuthenticated } = useAuth();

  return (
    <aside className="app-sidebar">
      <div className="sidebar-section-label">WORKSPACE</div>
      <nav className="sidebar-nav">
        {items.map((item) => {
          // If item is adminOnly and current user is not admin, hide or show with lock
          if (item.adminOnly && !isAdmin) {
            return null;
          }

          const Icon = navIcons[item.id] || LayoutDashboard;
          const isActive = activeItem === item.id;

          return (
            <button
              key={item.id}
              onClick={() => onSelect(item.id)}
              className={`nav-item ${isActive ? 'nav-item-active' : ''}`}
            >
              <Icon size={17} className="nav-icon" />
              <span className="nav-label">{item.label}</span>
              {item.adminOnly ? (
                <span className="nav-badge admin-badge">Admin</span>
              ) : item.id !== 'dashboard' ? (
                <span className="nav-badge">Phase {item.id === 'datasets' ? '3' : 'Later'}</span>
              ) : null}
            </button>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        {isAuthenticated ? (
          <div className="system-tag">
            <span className="system-tag-label">{user?.username}</span>
            <span className="system-tag-desc">Role: {user?.role}</span>
          </div>
        ) : (
          <div className="system-tag">
            <span className="system-tag-label">Phase 2</span>
            <span className="system-tag-desc">Auth & RBAC Ready</span>
          </div>
        )}
      </div>
    </aside>
  );
}
