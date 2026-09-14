# Event Platform

Full-stack event management platform. Vue frontend, Python FastAPI microservices on the backend, MySQL per service. Firebase Authentication is the identity layer: the frontend signs in directly against Firebase, and every service independently verifies the resulting ID token.

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

`axiosClient.js` creates authenticated clients for each microservice (ports 8001–8006), attaching a Firebase Bearer token to every request.

## Backend

Each microservice is an independent FastAPI app with its own MySQL database, Dockerfile, and `requirements.txt`.

```
services/
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
2. Axios sends `GET /events/123` directly to **event-service** (`:8002`)
3. `event-service` verifies the Firebase token and queries its Event DB; registration counts come from **registration-service**
4. Response returns directly to axios → Vue

## Run locally

Create a venv and install Python deps first. Alembic / PyMySQL live in those requirements — `python scripts/migrate.py` will fail without them.

```
python -m venv .venv
.venv\Scripts\activate
# macOS / Linux: source .venv/bin/activate
pip install -r services/user-service/requirements.txt
# repeat for the other services' requirements.txt (or at least user-service, which includes Alembic)
```

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

When you change a model, generate a revision from the **repo root** (this sets `DATABASE_URL` and `PYTHONPATH` for you — the Unix `DATABASE_URL=... alembic ...` one-liner does not work in Windows PowerShell):

```
python scripts/revision.py event-service -m "describe the change"
```

Replace `event-service` with the owning service folder (`user-service`, `venue-service`, …). Review the new file under `services/<service>/alembic/versions/`, then apply it with `python scripts/migrate.py --no-seed`.

Frontend:

```
cd frontend
npm install
npm run dev
```

Backend (from repo root, with the same venv already activated):

```
python scripts/dev-backend.py
```

Screens still use hardcoded demo data until they import the `src/api` service files.
