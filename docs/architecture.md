# ConnectSphere — architecture and how to run it

Developer guide for the Event Planning and Venue Booking system. Data model (tables, enums, FKs, ERD): [data-model.md](data-model.md).

## What you are looking at

Vue 3 frontend, FastAPI microservices, and **one shared MySQL instance with one schema per service**, running in local Docker. Firebase is the intended auth layer later; local demo login still uses a JWT from `user-service`.

`frontend/src/api/*.js` are **not** microservices. They are axios wrappers. Business logic and databases live under `services/`. The two talk only over HTTP.

```mermaid
flowchart LR
  Vue["Vue frontend :5173"] --> UserSvc["user-service :8001"]
  Vue --> EventSvc["event-service :8002"]
  Vue --> VenueSvc["venue-service :8003"]
  Vue --> EquipSvc["equipment-service :8004"]
  Vue --> RegSvc["registration-service :8005"]
  Vue --> NotifSvc["notification-service :8006"]
  UserSvc --> MySQL[("MySQL :3307")]
  EventSvc --> MySQL
  VenueSvc --> MySQL
  EquipSvc --> MySQL
  RegSvc --> MySQL
  NotifSvc --> MySQL
  EventSvc -->|"HTTP"| VenueSvc
  EventSvc -->|"HTTP"| EquipSvc
  EventSvc -->|"HTTP"| RegSvc
  EventSvc -->|"HTTP"| NotifSvc
```

There is **no repo-root `db/` folder**. Database data is stored in one Docker volume. Each service owns its schema through its own Alembic migration tree. `infra/` starts one MySQL instance and creates the six empty schemas.

Inter-service calls today are **HTTP**, not a message queue. A queue can be added later for notifications without changing the tables.

---

## Prerequisites

- Docker Desktop (for MySQL)
- Python 3.12+ with `venv`
- Node.js 18+ (Vite frontend)
- From the **repo root**, a venv with at least one service’s requirements (they share FastAPI / SQLAlchemy / Alembic):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r services/user-service/requirements.txt
pip install -r services/event-service/requirements.txt
pip install -r services/venue-service/requirements.txt
pip install -r services/equipment-service/requirements.txt
pip install -r services/registration-service/requirements.txt
pip install -r services/notification-service/requirements.txt
```

---

## When to run what

Think of three layers:

1. **Docker** — starts the shared MySQL *process* (or reuses data you already have).
2. **`python scripts/migrate.py`** — applies any *new* Alembic files, then seeds if tables were empty.
3. **Backend / frontend** — the apps. They do not create tables.

Alembic files live in git (`services/*/alembic/versions/`). Your laptop remembers what it already applied in a table named `alembic_version`. Migrate only runs files you do not have yet.

### A. You just `git clone` (first time on this laptop)

Do the full setup **once**:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r services/user-service/requirements.txt
# repeat pip install -r services/<name>/requirements.txt for the other services
cd frontend && npm install && cd ..

cd infra
docker compose up -d
cd ..
python scripts/migrate.py
```

Then start coding with backend + frontend (sections below). You now have the MySQL container, tables, and seed data.

### B. You already cloned; you sit down to code (no schema change)

```bash
# Docker Desktop must be running
cd infra
docker compose up -d               # skip if containers are already Up
cd ..
python scripts/dev-backend.py      # terminal 1
# terminal 2:
cd frontend && npm run dev
```

**Do not** `docker compose down -v`. **Do not** migrate. Your tables are still on disk.

### C. You `git pull` and *someone else* changed the database

If the pull added files under `services/*/alembic/versions/`:

```bash
cd infra && docker compose up -d && cd ..
python scripts/migrate.py --no-seed
```

`--no-seed` updates tables without inserting demo rows again. If seed is written to skip when tables already have data, plain `python scripts/migrate.py` is also fine.

If the pull only changed Vue/Python and **no** new `alembic/versions/` files: just `up -d` (if needed) and run the apps. No migrate.

### D. *You* want a new table / rename a column / new column

You author a new Alembic file. Teammates do **not** write SQL by hand.

1. Edit the SQLAlchemy model in the **owning** service (e.g. `services/venue-service/app/models/…`).
2. Generate a revision (example: venue DB):

```bash
python scripts/revision.py venue-service -m "add column foo to venues"
```

3. Open the new file in `alembic/versions/`, check it looks right, then apply it locally:

```bash
python scripts/migrate.py --no-seed
```

4. Commit the **model + the new version file**. Update `docs/data-model.md` if the design changed.
5. Everyone else: `git pull`, then **C**.

Never edit `0001_initial.py` after it has been shared. Always add `0002_…`, `0003_…`.

### E. Local DB is broken / you want a clean seed

This **wipes all MySQL data** on your machine:

```bash
cd infra
docker compose down -v
docker compose up -d
cd ..
python scripts/migrate.py
```

---

## Start everything (local)

Open **three** terminals from the repo root (with the venv activated in the backend one).

### 1. Databases

```bash
cd infra
docker compose up -d
cd ..
python scripts/migrate.py
```

`migrate.py` waits for MySQL, runs `alembic upgrade head` in every service, then seeds demo users / venues / events. Re-run after `git pull` when someone committed a new Alembic revision. Skip seed with `--no-seed`.

Nuclear reset (wipes all local data):

```bash
cd infra
docker compose down -v
docker compose up -d
cd ..
python scripts/migrate.py
```

### 2. Backend

```bash
python scripts/dev-backend.py
```

Or `npm run dev:backend`. Starts all FastAPI apps with `--reload`:

| Process | Port |
|---|---|
| user-service | 8001 |
| event-service | 8002 |
| venue-service | 8003 |
| equipment-service | 8004 |
| registration-service | 8005 |
| notification-service | 8006 |

Health check: `http://localhost:8001/health` (swap port per service). Interactive API docs: `http://localhost:8001/docs` (swap port). Index of all six specs: [api.md](api.md). The browser calls each service directly on its app port (8001–8006).

`dev-backend.py` sets `PYTHONPATH` to the repo root so `import shared` works.

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

Or from repo root: `npm run dev:frontend`. Vite defaults to **http://localhost:5173**.

Set an optional per-service URL with `VITE_USER_SERVICE_URL`, `VITE_EVENT_SERVICE_URL`, `VITE_VENUE_SERVICE_URL`, `VITE_EQUIPMENT_SERVICE_URL`, `VITE_REGISTRATION_SERVICE_URL`, or `VITE_NOTIFICATION_SERVICE_URL`. Local defaults are ports 8001–8006.

### Demo logins

Shown on the login screen. Seeded in MySQL and listed in `Test Data/credentials-valid.txt`:

| Email | Password | Role |
|---|---|---|
| organiser@connectsphere.com | organiser123 | Event Organiser |
| coordinator@connectsphere.com | coord123 | Event Coordinator |
| venue@connectsphere.com | venue123 | Venue Staff |
| tech@connectsphere.com | tech123 | Technical Support |
| attendee@connectsphere.com | attend123 | Attendee |

Login uses Firebase plus `GET /users/me`. `frontend/src/auth/users.data.js` is the on-screen demo list only.

---

## Ports (MySQL)

All services connect to the same MySQL instance on host port `3307`, but each uses its own schema and independent `alembic_version` table.

| Service | App | Schema | DB port |
|---|---|---|---|
| user-service | 8001 | `user` | 3307 |
| event-service | 8002 | `event` | 3307 |
| venue-service | 8003 | `venue` | 3307 |
| equipment-service | 8004 | `equipment` | 3307 |
| registration-service | 8005 | `registration` | 3307 |
| notification-service | 8006 | `notification` | 3307 |

Credentials (local only): user `connectsphere`, password `connectsphere`. Example URL:

```
mysql+pymysql://connectsphere:connectsphere@localhost:3307/user
```

---

## Repository layout

```
SPM_G6T3/
├── frontend/                 Vue 3 + Vite
├── services/                 FastAPI microservices
├── shared/                   Python used by every backend service
├── infra/                    Docker Compose — local MySQL only
├── scripts/                  migrate, seed, start all backends
├── Test Data/                shared acceptance-test credentials
├── e2e/                      Playwright browser and API acceptance tests
├── docs/                     architecture, API, data model, testing
├── package.json              development and acceptance-test commands
└── README.md
```

### `frontend/`

```
frontend/
├── index.html
├── package.json
├── vite.config.js
└── src/
    ├── main.js
    ├── App.vue
    ├── firebase.js              placeholder — Auth later
    ├── api/                     axios wrappers → owning microservice
    │   ├── axiosClient.js
    │   ├── userService.js
    │   ├── eventService.js
    │   ├── venueService.js
    │   ├── equipmentService.js
    │   ├── registrationService.js
    │   └── notificationService.js
    ├── views/                   routes: Landing, Login, Dashboard shell
    ├── features/                one folder per dashboard tab
    │   ├── dashboard/
    │   ├── venue-catalogue/
    │   └── browse-events/
    ├── auth/users.data.js       demo credentials (UI)
    ├── store/session.js         client session
    ├── config/roles.js          tabs per role
    ├── router/index.js
    ├── composables/
    └── components/shared/
```

### `services/`

Each service with a DB:

```
services/<name>/
├── app/
│   ├── main.py              FastAPI app
│   ├── core/config.py       DATABASE_URL, CORS
│   ├── db/session.py        engine + session (not the MySQL files)
│   ├── models/              SQLAlchemy — one module per table
│   ├── schemas/             Pydantic API shapes (camelCase JSON)
│   ├── routers/             HTTP endpoints
│   └── services/            business rules
├── alembic/                 schema migrations (source of truth)
├── alembic.ini
├── Dockerfile
└── requirements.txt
```

`event-service` also has `app/orchestration/` — HTTP clients to other services (no cross-DB joins).

### `infra/`

Starts one MySQL instance and creates empty service schemas. It does **not** define tables.

```
infra/
├── docker-compose.yml
└── mysql/init/
    └── schemas.sql          Creates all six schemas and grants (first boot only)
```

### `scripts/`

| Script | Purpose |
|---|---|
| `dev-backend.py` | uvicorn all services |
| `migrate.py` | wait for MySQL → alembic upgrade → seed |
| `prepare-acceptance-tests.py` | start MySQL, migrate, and seed before Playwright |
| `revision.py` | `alembic revision --autogenerate` for one service (Windows-safe) |
| `seed.py` | demo rows (called by migrate unless `--no-seed`) |

### `shared/`

```
shared/
├── auth/tokens.py      demo JWT; Firebase verify stub
├── openapi.py          FastAPI titles, Swagger Bearer auth, error examples
├── schemas/
├── exceptions/
└── logging/
```

### `docs/`

| File | Purpose |
|---|---|
| `architecture.md` | this file |
| `api.md` | OpenAPI / Swagger index (ports, auth, role gates) |
| `data-model.md` | tables, enums, conflict/capacity rules, ERD |
| `testing/` | How to run SPM-43 / SPM-45 and the AC-to-spec map |

---

## Request path (example)

`getEvent(eventId)`:

1. Vue → `frontend/src/api/eventService.js`
2. `GET /events/{id}` → **event-service :8002**
3. event-service verifies the Firebase token, reads `event` DB, and gets the registration count via HTTP to **registration-service**
4. JSON returns directly to Vue

---

## Changing the schema

1. Edit models in the owning service (`services/venue-service/app/models/…`).
2. Generate a revision, review the file, commit it:

```bash
python scripts/revision.py venue-service -m "describe the change"
```

3. Teammates: `git pull` then `python scripts/migrate.py`.
4. Update [data-model.md](data-model.md) so the doc matches the code.

Do not use `create_all()` to evolve tables. Do not put table DDL in `infra/mysql/init/` (the init script only creates empty schemas and grants access).

Because all schemas share one MySQL process and volume, an instance outage affects every service. Back up or restore individual service data with schema-scoped dumps when isolation is required.

---

## Current gaps (so nobody is surprised)

- Many dashboard tabs are still placeholders.
- Venue catalogue and browse-events still read hardcoded `.data.js` until wired to `src/api`.
- Login UI is still client-side; `user-service` already has `/users/login` for when you wire it.
- Notifications persist in MySQL; sending is still a stub (print / queued email).
