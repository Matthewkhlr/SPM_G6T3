# Event Platform

Full-stack event management platform. Vue frontend, Python FastAPI microservices on the backend, MySQL per service. Firebase Authentication is the intended identity layer; local demo login still issues a JWT from `user-service` until Firebase is wired.

**Developers:** start here — [docs/architecture.md](docs/architecture.md) (file tree, ports, how to run frontend / backend / MySQL). Data model: [docs/data-model.md](docs/data-model.md).

**Important distinction:** `frontend/src/api/*.js` files are NOT microservices — they are thin axios wrappers that send HTTP requests. The actual microservices (business logic, database access) are Python FastAPI apps living under `services/`. The two are separate codebases that only communicate over HTTP.

The data model (tables, enums, conflict/capacity rules) lives in [docs/data-model.md](docs/data-model.md).

## Top-Level Structure

```
├── frontend/          # Vue 3 app
├── services/          # Python FastAPI microservices
├── shared/            # Code shared across backend services
├── infra/             # docker-compose, MySQL init scripts
├── scripts/           # local migrate/seed and backend launcher
└── docs/              # architecture / data model
```

This folder is laid out to drop into the event-platform repo. The UI stays Vue (`views/`, `features/`, `composables/`) instead of React `pages/` / `hooks/`. The API files match the platform README 1:1.

## Frontend API

```
frontend/src/api/
  axiosClient.js          Shared axios instance + auth interceptor
  userService.js
  eventService.js
  venueService.js
  equipmentService.js
  registrationService.js
  notificationService.js
```

`axiosClient.js` points at the API gateway (`http://localhost:8000`). Attach a Bearer token after login (`localStorage.idToken`), then swap that for Firebase `getIdToken()` in the interceptor.

## Backend

Each microservice is an independent FastAPI app with its own MySQL database, Dockerfile, and `requirements.txt`.

```
services/
├── api-gateway/            # :8000  verifies tokens, forwards to services
├── user-service/          # :8001  user-db :3307
├── event-service/          # :8002  event-db :3309  (orchestrator)
├── venue-service/         # :8003  venue-db :3308
├── equipment-service/     # :8004  equipment-db :3310
├── registration-service/  # :8005  registration-db :3311
└── notification-service/  # :8006  notification-db :3312
```

Every service with a database follows:

| Folder | Purpose |
|---|---|
| `app/main.py` | FastAPI app, includes routers |
| `app/routers/` | Endpoints |
| `app/models/` | SQLAlchemy ORM — one per table |
| `app/schemas/` | Pydantic request/response models |
| `app/services/` | Business rules |
| `app/db/session.py` | Engine/session for that service's DB |
| `app/core/config.py` | Env vars |
| `alembic/` | Migrations (source of truth for schema) |

`event-service/app/orchestration/` calls other services over HTTP (no cross-DB joins). Cross-service IDs (`event_id`, `user_id`, `venue_id`) are logical foreign keys only.

Each service defaults `DATABASE_URL` to its local Docker MySQL instance, for example:

```
mysql+pymysql://connectsphere:connectsphere@localhost:3307/user
```

Schema is owned by Alembic. Do not use `create_all()` to evolve tables.

## Shared

```
shared/
├── auth/          Firebase-ready token helpers (JWT for local demo)
├── schemas/       Common Pydantic models
├── exceptions/    Shared HTTP errors
└── logging/       Logging notes
```

## Request flow — `getEvent(eventId)`

1. Vue calls `getEvent(123)` → `frontend/src/api/eventService.js`
2. Axios sends `GET /events/123` → **api-gateway** (verifies token)
3. Gateway forwards to **event-service** → `services/event-service/app/routers/event.py`
4. `event-service` queries its Event DB; registration counts come from **registration-service**
5. Response flows back through the gateway → axios → Vue

## Run locally

Start MySQL (required), then migrate + seed so every teammate has the same schema:

```
cd infra
docker compose up -d
cd ..
python scripts/migrate.py
```

`scripts/migrate.py` waits until each MySQL port is up, runs `alembic upgrade head` in every service, then inserts demo users/venues/events. Re-run it after `git pull` when someone committed a new Alembic revision. Use `--no-seed` to skip demo data.

If a local database is hopelessly out of date, wipe volumes and start clean:

```
cd infra
docker compose down -v
docker compose up -d
cd ..
python scripts/migrate.py
```

When you change a model, generate a revision in that service, review it, and commit it:

```
cd services/event-service
DATABASE_URL=mysql+pymysql://connectsphere:connectsphere@localhost:3309/event alembic revision --autogenerate -m "describe the change"
```

Frontend:

```
cd frontend
npm install
npm run dev
```

Backend (from repo root, after `pip install -r services/user-service/requirements.txt` in a venv — install each service's requirements, or at least one of them plus Alembic):

```
python scripts/dev-backend.py
```

Screens still use hardcoded demo data until they import the `src/api` service files.
