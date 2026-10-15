import React from 'react';
import { RefreshCw, CheckCircle2, XCircle, Loader2, LogOut, User as UserIcon, Shield } from 'lucide-react';
import { formatTimestamp } from '../utils/formatters';
import { useAuth } from '../context/AuthContext';

export function Header({ status, lastChecked, onRefresh, activePageLabel, onNavigate }) {
  const { user, isAuthenticated, logout } = useAuth();
  const isConnected = status === 'connected';
  const isChecking = status === 'checking';

  const handleLogout = () => {
    logout();
    if (onNavigate) {
      onNavigate('login');
    }
  };

  return (
    <header className="app-header">
      <div className="header-left">
        <div className="brand-badge" onClick={() => onNavigate && onNavigate(isAuthenticated ? 'dashboard' : 'login')} style={{ cursor: 'pointer' }}>
          <span className="brand-dot"></span>
          <span className="brand-title">AI Data Analyst Agent</span>
        </div>
        <span className="header-divider">/</span>
        <span className="current-view-name">{activePageLabel}</span>
      </div>

      <div className="header-right">
        {/* Backend health status indicator */}
        <div
          className={`status-pill ${
            isConnected ? 'status-connected' : isChecking ? 'status-checking' : 'status-disconnected'
          }`}
          title={lastChecked ? `Last checked: ${formatTimestamp(lastChecked)}` : ''}
        >
          {isChecking ? (
            <>
              <Loader2 className="status-icon spin" size={13} />
              <span>Checking...</span>
            </>
          ) : isConnected ? (
            <>
              <CheckCircle2 className="status-icon" size={13} />
              <span className="status-text">Backend Connected</span>
            </>
          ) : (
            <>
              <XCircle className="status-icon" size={13} />
              <span className="status-text">Backend Disconnected</span>
            </>
          )}
        </div>

        <button
          onClick={onRefresh}
          className="refresh-btn"
          title="Recheck backend connection"
          disabled={isChecking}
        >
          <RefreshCw size={13} className={isChecking ? 'spin' : ''} />
          <span>Refresh</span>
        </button>

        {/* User Profile & Auth Actions */}
        {isAuthenticated ? (
          <div className="user-profile-widget">
            <div className="user-info-chip">
              <UserIcon size={14} className="user-icon" />
              <span className="user-username">{user?.username}</span>
              <span className={`role-badge ${user?.role === 'admin' ? 'role-badge-admin' : 'role-badge-user'}`}>
                {user?.role === 'admin' && <Shield size={10} style={{ marginRight: 2 }} />}
                {user?.role}
              </span>
            </div>
            <button
              onClick={handleLogout}
              className="logout-btn"
              title="Sign Out"
            >
              <LogOut size={13} />
              <span>Logout</span>
            </button>
          </div>
        ) : (
          <div className="auth-nav-buttons">
            <button
              onClick={() => onNavigate && onNavigate('login')}
              className="btn-auth-link"
            >
              Sign In
            </button>
            <button
              onClick={() => onNavigate && onNavigate('signup')}
              className="btn-auth-pill"
            >
              Sign Up
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
