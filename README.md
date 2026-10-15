# AI Data Analyst Agent

A high-performance, modular platform for automated and conversational data analysis, intelligent data profiling, quality remediation, anomaly detection, forecasting, and interactive reporting.

---

## Current Status

- **Phase 1 — Foundation: COMPLETED**
- **Phase 2 — Database + Authentication + Authorization: COMPLETED**

Verified:
- SQLAlchemy ORM database layer with SQLite development engine and migrations-ready structure.
- User model with secure attributes (`id`, `username`, `email`, `hashed_password`, `role`, `is_active`, `created_at`, `updated_at`).
- Argon2 password hashing via `pwdlib[argon2]` (no plaintext passwords stored or returned).
- JWT Authentication (`sub`, `role`, `exp`) with configurable expiration and HMAC-SHA256 signature validation.
- Role-based authorization (`user` vs `admin`) enforced at the API dependency level (`require_role("admin")`).
- Safe user registration (`POST /api/auth/signup`) and authentication (`POST /api/auth/login`).
- Current user profile endpoint (`GET /api/auth/me`).
- Admin user listing endpoint (`GET /api/users`) returning `403 Forbidden` for non-admin users.
- Administrative user seed CLI command (`python -m app.commands.seed_admin`).
- Frontend AuthContext with session restoration on startup, login/signup forms, logout, and client-side route guards.
- All 18 automated backend tests passed.
- Production React build passed.

---

## Technology Stack

### Frontend
- **Framework**: React 19 + JavaScript (JSX)
- **Tooling**: Vite 8
- **Networking**: Axios with centralized request/response interceptors & token injection
- **State Management**: React Context (`AuthContext`)
- **Icons**: Lucide React
- **Styling**: Pure Modern CSS with dark data-product theme and responsive layout

### Backend
- **Framework**: FastAPI (async REST framework)
- **Database**: SQLite (dev) / SQLAlchemy 2.0 ORM
- **Password Security**: Argon2 (`pwdlib[argon2]`)
- **Tokens**: PyJWT (HMAC-SHA256)
- **ASGI Server**: Uvicorn
- **Validation & Schemas**: Pydantic v2 & Pydantic Settings
- **Configuration**: Python Dotenv & Environment-based config
- **Testing**: Pytest & FastAPI TestClient (HTTPX)

---

## Architecture & Design Principles

```text
DataAnalystAgentAi/
│
├── frontend/
│   ├── src/
│   │   ├── components/         # Pure UI components (Header, Sidebar, Placeholders)
│   │   ├── context/            # AuthContext provider and useAuth hook
│   │   ├── pages/              # View-level components (Dashboard, Login, Signup, AdminUsers)
│   │   ├── services/           # Centralized API service & token manager (api.js)
│   │   ├── hooks/              # Custom hooks (useHealthCheck.js)
│   │   ├── utils/              # Helper utilities (formatters.js)
│   │   ├── types/              # Type constants and navigation configurations
│   │   ├── App.jsx             # Shell layout, route protection, and navigation state
│   │   ├── index.css           # Modern design system & token definitions
│   │   └── main.jsx            # React root mount
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/         # Route handlers (auth.py, users.py, health.py)
│   │   │   └── router.py       # Global API router aggregator
│   │   ├── commands/           # CLI commands (seed_admin.py)
│   │   ├── core/               # App config, security (Argon2/JWT), errors, logger, dependencies
│   │   ├── database/           # Engine, sessionmaker, init_db, get_db (database.py)
│   │   ├── models/             # SQLAlchemy ORM models (user.py)
│   │   ├── schemas/            # Pydantic request/response schemas (auth.py, user.py)
│   │   ├── services/           # Decoupled business logic (auth_service.py, health_service.py)
│   │   ├── utils/              # Utility helpers
│   │   └── main.py             # FastAPI factory, lifespan, and CORS setup
│   ├── tests/                  # Automated pytest suite (test_auth.py, test_health.py, startup)
│   ├── requirements.txt
│   ├── .env.example
│   └── .env
│
├── docs/                       # Architectural documentation
├── .gitignore
└── README.md
```

---

## Authentication & Authorization Architecture

### 1. User Model
Located in `backend/app/models/user.py`:
- `id`: Integer primary key, autoincrement
- `username`: String(50), unique, indexed, required
- `email`: String(255), unique, indexed, required
- `hashed_password`: String(255), required (stores Argon2 hash)
- `role`: String(20), default `"user"`, required
- `is_active`: Boolean, default `True`, required
- `created_at`: DateTime (UTC), server default
- `updated_at`: DateTime (UTC), server default, auto-updated

### 2. Password Hashing (Argon2)
Located in `backend/app/core/security.py`:
- `hash_password(password: str) -> str`: Generates high-entropy Argon2 hashes using `pwdlib`.
- `verify_password(password: str, hashed_password: str) -> bool`: Verifies candidate passwords without exposing hashes or timing leaks.
- Passwords are never logged, never returned in API responses, and never stored as plaintext.

### 3. JWT Authentication & Token Lifecycle
- Standard Bearer token authentication over HTTP `Authorization: Bearer <token>` header.
- Token payload structure:
  ```json
  {
    "sub": "<user_id>",
    "role": "user",
    "username": "anu",
    "exp": 1791370000
  }
  ```
- Expiration: Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (defaults to 30 minutes).
- Secret key: Configured via `JWT_SECRET_KEY` in environment variables.

### 4. Dependency Injection & RBAC
Located in `backend/app/core/dependencies.py`:
- `get_current_user`: Validates signature, verifies expiration, validates subject, checks database record existence, and verifies `is_active == True`. Returns `HTTP 401 Unauthorized` on failure.
- `require_role(allowed_role)`: Enforces role permissions. Returns `HTTP 403 Forbidden` if a non-admin attempts to access an administrative endpoint.

### 5. Frontend Token Storage Decision
Bearer tokens are managed within `frontend/src/services/api.js`. The token is cached in-memory and synchronized with `localStorage` under key `ai_analyst_token`. Axios request interceptors automatically append `Authorization: Bearer <token>` to all authenticated requests. On logout or 401 expiration, the token is cleared from memory and storage, resetting application state cleanly to the login view.

---

## API Endpoints

| Method | Endpoint | Access | Description |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/health` | Public | System health check |
| `POST` | `/api/auth/signup` | Public | Register new user account (role: `user`) |
| `POST` | `/api/auth/login` | Public | Authenticate credentials and receive JWT |
| `GET` | `/api/auth/me` | Authenticated | Retrieve current user profile |
| `GET` | `/api/users` | Admin Only | List all registered users |

---

## Environment Variables

Configured in `backend/.env` (modeled after `backend/.env.example`):

```ini
# Application Configuration
APP_NAME=AI Data Analyst Agent
APP_ENV=development

# Frontend & CORS Configuration
FRONTEND_URL=http://localhost:5173

# Backend Server Configuration
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8000

# Database Configuration
DATABASE_URL=sqlite:///./data_analyst.db

# JWT Authentication
JWT_SECRET_KEY=change-to-a-secure-random-32-char-key-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
```

---

## Administrative Account Creation

Public registration (`/api/auth/signup`) explicitly forbids setting the `admin` role. Administrative users must be created through the backend CLI seed tool:

```powershell
cd backend
python -m app.commands.seed_admin --username admin --email admin@example.com --password YourSecureAdminPassword123!
```

Or run interactively (will prompt securely for password):
```powershell
python -m app.commands.seed_admin --username admin --email admin@example.com
```

---

## Installation & Running

### 1. Backend Setup

```powershell
cd backend
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```
- API Health Endpoint: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- Interactive Swagger Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 2. Frontend Setup

```powershell
cd frontend
npm install
npm run dev
```
- Application UI: [http://localhost:5173/](http://localhost:5173/)

---

## Running Automated Tests

Run the complete backend test suite:
```powershell
python -m pytest backend/tests -v
```

Run frontend production build verification:
```powershell
cd frontend
npm run build
```

---

## Project Roadmap

| Phase | Milestone | Status |
| :--- | :--- | :--- |
| **Phase 1** | **Project Foundation & Frontend-Backend Connection** | **COMPLETED** |
| **Phase 2** | **Database + Authentication + Role-Based Authorization** | **COMPLETED** |
| Phase 3 | Dataset Ingestion (CSV / XLSX / XLS / Multi-file) | Planned |
| Phase 4 | Data Profiling & Statistical Summaries | Planned |
| Phase 5 | Data Cleaning & Transformation Pipeline | Planned |
| Phase 6 | Anomaly & Outlier Detection Engine | Planned |
| Phase 7 | Machine Learning Prediction & Forecasting | Planned |
| Phase 8 | Natural Language Analysis ("Ask Analyst" with AI) | Planned |
| Phase 9 | Comprehensive Reports & Automated Export | Planned |
