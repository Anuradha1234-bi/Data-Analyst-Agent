# Architecture Overview — AI Data Analyst Agent

## System Design Philosophy

The AI Data Analyst Agent is engineered with strict separation of concerns, modular scalability, and deterministic API contracts.

```text
┌─────────────────────────────────────────────────────────────┐
│                       React Frontend                        │
│   (Vite + React 19 + Axios + Responsive Data Dashboard)    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP / JSON
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Backend                        │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                    API Router Layer                   │  │
│  │                 (app/api/routes/*.py)                 │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │                              │
│  ┌───────────────────────────▼───────────────────────────┐  │
│  │                     Service Layer                     │  │
│  │                  (app/services/*.py)                  │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │                              │
│  ┌───────────────────────────▼───────────────────────────┐  │
│  │                 Data Models & Schemas                 │  │
│  │            (app/schemas/*.py, app/models/)            │  │
│  └───────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │             Core Infrastructure & Utilities           │  │
│  │            (app/core/config.py, errors, logger)       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Layer Responsibilities

1. **Presentation Layer (`frontend/src/`)**:
   - `components/`: Pure UI components (Header, Sidebar, Placeholders).
   - `pages/`: View-level containers (Dashboard, Datasets, etc.).
   - `services/`: Axios HTTP client and centralized API abstraction.
   - `hooks/`: Reusable React state management (e.g. `useHealthCheck`).
   - `utils/`: Pure utility helpers (formatters, data converters).
   - `types/`: Type definitions and constants.

2. **Backend API Routing (`backend/app/api/`)**:
   - Exposes RESTful endpoints.
   - Strictly delegates business logic to services.
   - Enforces Pydantic input and output validation.

3. **Backend Service Layer (`backend/app/services/`)**:
   - Pure Python business logic.
   - Decoupled from HTTP frameworks, facilitating unit testing.

4. **Backend Core Layer (`backend/app/core/`)**:
   - Centralized configuration via `pydantic-settings`.
   - Centralized error handling and standard error responses.
   - Structured logging.

## Roadmap & Phased Implementation

- [x] **Phase 1: Project Foundation & Frontend-Backend Connection**
- [ ] **Phase 2: Dataset Ingestion (CSV / XLSX / XLS multi-file support)**
- [ ] **Phase 3: Data Profiling & Statistical Summaries**
- [ ] **Phase 4: Data Cleaning & Transformation Pipeline**
- [ ] **Phase 5: Anomaly & Outlier Detection**
- [ ] **Phase 6: Predictive Analytics & Forecasting**
- [ ] **Phase 7: Natural Language Analysis ("Ask Analyst")**
- [ ] **Phase 8: Comprehensive Reporting & Export Engine**
