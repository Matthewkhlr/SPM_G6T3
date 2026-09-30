# ConnectSphere API

Interactive OpenAPI (Swagger) docs for each FastAPI microservice. The spec is generated from routers and Pydantic models — do not hand-write a separate `swagger.yaml`.

Start the backends (`python scripts/dev-backend.py`), then open `/docs` on the service you need. `/redoc` is the same spec in a read-only layout. `/openapi.json` is the machine-readable file.

| Service | Port | Swagger UI | ReDoc |
|---|---|---|---|
| user-service | 8001 | http://localhost:8001/docs | http://localhost:8001/redoc |
| event-service | 8002 | http://localhost:8002/docs | http://localhost:8002/redoc |
| venue-service | 8003 | http://localhost:8003/docs | http://localhost:8003/redoc |
| equipment-service | 8004 | http://localhost:8004/docs | http://localhost:8004/redoc |
| registration-service | 8005 | http://localhost:8005/docs | http://localhost:8005/redoc |
| notification-service | 8006 | http://localhost:8006/docs | http://localhost:8006/redoc |

`GET /health` on every service is public. Every other route expects a Firebase ID token.

## Auth in Swagger

1. Sign in through the Vue app with a [demo account](architecture.md#demo-logins).
2. Copy the ID token (browser console: the Network tab on any API call → `Authorization: Bearer …`, token only).
3. In `/docs`, click **Authorize**, paste the token (not the word `Bearer`), and **Try it out**.

Role gates (enforced by forwarding the token to `GET /users/me`):

| Action | Role |
|---|---|
| `POST /events` | `organiser` |
| `GET /events/upcoming/technical` | `techsupport` |
| `POST /events/{id}/assign-coordinator` | `coordinator` |
| `GET /venues`, `GET /venues/{id}`, `GET /venues/{id}/activity-log` | `coordinator`, `venue`, `techsupport` |
| `POST /venues`, `PATCH /venues/{id}`, `POST /venues/{id}/retire` | `venue` |
| `POST /venues/suitability` | `coordinator`, `venue` |
| `POST /venues/bookings` | `coordinator` assigned to the event (SPM-63) |
| `GET /venues/bookings`, `GET /venues/bookings/{id}` | `coordinator`, `venue` |
| `POST /venues/bookings/{id}/withdraw` | `coordinator` who sent the request |
| `POST /venues/bookings/{id}/approve` or `/reject` | `venue` |
| `POST /equipment/requests` | `coordinator` |
| `POST /equipment/requests/{id}/review`, `/reserve`, or `/unavailable` | `techsupport` |
| `PATCH /equipment/requests/{id}` | refused |
| `POST /equipment/availability` with `eventId` | signed-in caller |
| `POST /equipment/reservations/{id}/release` | `techsupport` |

JSON is camelCase. Tables and conflict rules: [data-model.md](data-model.md). How to run the stack: [architecture.md](architecture.md). Acceptance tests: [testing/README.md](testing/README.md).
