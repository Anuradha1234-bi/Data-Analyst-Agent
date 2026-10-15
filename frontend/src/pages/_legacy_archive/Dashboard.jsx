import React from 'react';
import {
  Server,
  Activity,
  CheckCircle2,
  XCircle,
  Database,
  ArrowRight,
  Code2,
  Cpu,
} from 'lucide-react';
import { formatTimestamp } from '../utils/formatters';

export function Dashboard({ healthStatus, healthData, lastChecked, errorDetails, onCheckHealth }) {
  const isConnected = healthStatus === 'connected';

  return (
    <div className="page-container dashboard-page">
      <div className="hero-banner">
        <h1 className="hero-title">AI Data Analyst Agent</h1>
        <p className="hero-subtitle">
          Upload and analyze your datasets with intelligent profiling, cleaning,
          anomaly detection, prediction, and natural-language analysis.
        </p>
      </div>

      <div className="cards-grid">
        {/* Backend Status Card */}
        <div className={`status-card ${isConnected ? 'card-connected' : 'card-disconnected'}`}>
          <div className="card-header">
            <div className="card-header-left">
              <Server size={20} className="card-header-icon" />
              <h2 className="card-title">Backend Status</h2>
            </div>
            <div className={`status-indicator-badge ${isConnected ? 'badge-ok' : 'badge-err'}`}>
              {isConnected ? (
                <>
                  <CheckCircle2 size={14} />
                  <span>Connected</span>
                </>
              ) : (
                <>
                  <XCircle size={14} />
                  <span>Disconnected</span>
                </>
              )}
            </div>
          </div>

          <div className="card-body">
            <div className="status-display-large">
              <span className={`status-state-pill ${isConnected ? 'pill-connected' : 'pill-disconnected'}`}>
                {isConnected ? 'Backend Connected' : 'Backend Disconnected'}
              </span>
            </div>

            <div className="meta-details">
              <div className="meta-row">
                <span className="meta-label">Service:</span>
                <span className="meta-value">
                  {healthData?.service || 'AI Data Analyst Agent'}
                </span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Health API:</span>
                <span className="meta-value code-pill">GET /api/health</span>
              </div>
              <div className="meta-row">
                <span className="meta-label">Last Checked:</span>
                <span className="meta-value">{formatTimestamp(lastChecked)}</span>
              </div>
              {errorDetails && (
                <div className="meta-row error-row">
                  <span className="meta-label">Diagnostic:</span>
                  <span className="meta-value error-message">
                    {errorDetails.message || 'Cannot reach API server at http://127.0.0.1:8000'}
                  </span>
                </div>
              )}
            </div>

            <div className="card-actions">
              <button onClick={onCheckHealth} className="btn-secondary">
                <Activity size={14} />
                <span>Test Health Endpoint</span>
              </button>
              <a
                href="http://127.0.0.1:8000/docs"
                target="_blank"
                rel="noreferrer"
                className="btn-link"
              >
                <Code2 size={14} />
                <span>Swagger OpenAPI Docs</span>
                <ArrowRight size={12} />
              </a>
            </div>
          </div>
        </div>

        {/* System Capabilities Overview */}
        <div className="architecture-card">
          <div className="card-header">
            <div className="card-header-left">
              <Cpu size={20} className="card-header-icon" />
              <h2 className="card-title">Phase 1 Foundation</h2>
            </div>
            <span className="tag-ready">READY</span>
          </div>

          <div className="card-body">
            <p className="architecture-desc">
              The full-stack communication layer between Vite React and FastAPI is verified and
              operational. Subsequent analytical features are modularly staged.
            </p>

            <div className="features-checklist">
              <div className="feature-item active">
                <CheckCircle2 size={16} className="feature-check" />
                <span>FastAPI Modular Service Architecture</span>
              </div>
              <div className="feature-item active">
                <CheckCircle2 size={16} className="feature-check" />
                <span>Centralized Error Handling & CORS</span>
              </div>
              <div className="feature-item active">
                <CheckCircle2 size={16} className="feature-check" />
                <span>Pydantic v2 Type-Safe API Contracts</span>
              </div>
              <div className="feature-item active">
                <CheckCircle2 size={16} className="feature-check" />
                <span>React Shell with Responsive Health State</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
