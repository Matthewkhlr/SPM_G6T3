# Event Platform

Full-stack event management platform. Vue frontend, Python FastAPI microservices on the backend, MySQL per service. Firebase Authentication is the intended identity layer; local demo login still issues a JWT from `user-service` until Firebase is wired.

**Important distinction:** `frontend/src/api/*.js` files are NOT microservices — they are thin axios wrappers that send HTTP requests. The actual microservices (business logic, database access) are Python FastAPI apps living under `services/`. The two are separate codebases that only communicate over HTTP.

## Top-Level Structure

```
├── frontend/          # Vue 3 app
├── services/          # Python FastAPI microservices
├── shared/            # Code shared across backend services
├── infra/             # docker-compose, MySQL init scripts
└── docs/              # architecture/ERD diagrams
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
├── user-service/          # :8001  User DB
├── event-service/          # :8002  Event Info + Event Change (orchestrator)
├── venue-service/         # :8003  Venue Info + Venue Booking
├── equipment-service/     # :8004  Equipment Info / unit / request
├── registration-service/  # :8005  Registration + Attendee Registration
└── notification-service/  # :8006  email/SMS/push — no dedicated DB
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
| `alembic/` | Migrations |

`event-service/app/orchestration/` calls other services over HTTP (no cross-DB joins).

Local `uvicorn` defaults to SQLite so you can run without Docker. Point `DATABASE_URL` at MySQL when `infra/docker-compose.yml` is up:

```
mysql+pymysql://connectsphere:connectsphere@localhost:3307/user
```

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
4. `event-service` queries its Event Info DB; registration counts come from **registration-service**
5. Response flows back through the gateway → axios → Vue

## Run locally

Frontend:

```
cd frontend
npm install
npm run dev
```

Backend (from repo root, after `pip install -r services/user-service/requirements.txt` in a venv):

```
python scripts/dev-backend.py
```

MySQL (optional):

```
cd infra
docker compose up -d
```

Screens still use hardcoded demo data until they import the `src/api` service files.
