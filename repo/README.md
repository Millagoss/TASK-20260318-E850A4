# Activity Registration Platform

FastAPI + Vue 3 application for:
- applicant registration/material submission
- reviewer workflow and audit trail
- financial management with budget warnings
- system admin operations (metrics, alerts, backups, exports, user management)

## Stack

- Backend: FastAPI, SQLAlchemy, PostgreSQL
- Frontend: Vue 3 (Vite, TypeScript), Pinia, Vue Router
- Infra: Docker Compose

## Run (Docker)

1) Create `.env` from template:

```bash
# macOS/Linux
cp .env.example .env

# Windows PowerShell
Copy-Item .env.example .env
```

2) Fill required values in `.env`:
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `JWT_SECRET`
- `WHITELIST_ENCRYPTION_KEY` (any strong secret, or a `Fernet.generate_key()` string)
- `FEATURE_DUPLICATE_CHECK` (`false` by default)
- `VITE_API_BASE` (optional; API origin for the Vue app, default `http://localhost:8000` in code)

### Local dev without Docker (optional)

Backend: from `repo/backend`, install deps, set `DATABASE_URL`, `JWT_SECRET`, `WHITELIST_ENCRYPTION_KEY`, then run Uvicorn as you prefer.

Frontend: from `repo/frontend`, create `.env` with `VITE_API_BASE=http://localhost:8000` if needed, then `npm install` and `npm run dev`.

### Tests (backend)

```bash
cd backend
pytest
```

3) Start stack:

```bash
docker compose down -v
docker compose up --build -d
```

Open:
- Frontend: `http://localhost:5173`
- Backend API docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`

## Environment

`docker-compose.yml` now requires env-injected secrets/config and fails fast when missing.

## Auth and roles

Use `/register` (or `/signup` alias) to create users, then `/login`.

Supported roles:
- `Applicant`
- `Reviewer`
- `FinancialAdmin`
- `SystemAdmin`

Navigation is role-based via sidebar.

## Main pages by role

- Applicant
  - `/wizard` (upload materials, validation, deadlines)
- Reviewer
  - `/reviewer` (review queue, state transitions, batch apply, comments, audit trail)
- FinancialAdmin
  - `/financial` (accounts, transactions, invoice upload, aggregations, budget warning flow)
- SystemAdmin
  - `/system-admin` (metrics, thresholds, alerts, whitelist policies, backup/recovery, exports)
  - `/user-management` (list users, edit username/role, block/unblock)

## Common dev commands

Rebuild only backend:

```bash
docker compose up --build -d backend
```

Rebuild only frontend:

```bash
docker compose up --build -d frontend
```

Restart services:

```bash
docker compose restart backend frontend
```

View logs:

```bash
docker compose logs -f backend
docker compose logs -f frontend
```

## Notes

- Current setup uses SQLAlchemy `create_all` on startup (no production migration flow yet).
- Backups are stored in `/app/backups` (mounted Docker volume). Compose includes a `backup_scheduler` service that runs `pg_dump` daily into the same volume; `/admin/backup` remains available for on-demand dumps via `scripts/daily_backup.sh`.
- Whitelist policies are encrypted at rest; `WHITELIST_ENCRYPTION_KEY` may be a normal secret (derived) or a standard Fernet key.
