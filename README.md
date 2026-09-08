# Event Platform

Full-stack event management platform. React frontend, Python FastAPI microservices on the backend, MySQL per service, Firebase Authentication for identity.

**Important distinction:** `frontend/src/api/*.js` files are NOT microservices — they are thin axios wrappers that send HTTP requests. The actual microservices (business logic, database access) are Python FastAPI apps living under `services/`. The two are separate codebases that only communicate over HTTP.

## Top-Level Structure

```
event-platform/
├── frontend/          # React app (see "Frontend" section below)
├── services/          # Python FastAPI microservices (see "Backend" section below)
├── shared/            # Code shared across backend services
├── infra/             # docker-compose, MySQL init scripts
└── docs/              # architecture/ERD diagrams
```

---

# Frontend

React frontend for the event management platform. Talks to backend microservices through a single API Gateway, using Firebase Authentication for identity.

## File Structure

```
frontend/
├── src/
│   ├── api/                        # All backend communication lives here
│   │   ├── axiosClient.js          # Shared axios instance + auth interceptor
│   │   ├── userService.js          # User Service (auth/profile/RBAC)
│   │   ├── eventService.js         # Event Service (orchestrator)
│   │   ├── venueService.js         # Venue Service
│   │   ├── equipmentService.js     # Equipment Service
│   │   ├── registrationService.js  # Registration Service
│   │   └── notificationService.js  # Notification Service
│   │
│   ├── components/                 # Reusable UI pieces (buttons, cards, forms)
│   ├── pages/                      # Full page views (Dashboard, EventDetails, Login)
│   ├── hooks/                      # Custom React hooks
│   ├── context/
│   │   └── AuthContext.jsx         # Firebase auth state, wraps the app
│   ├── firebase.js                 # Firebase app initialization/config
│   └── App.jsx
│
├── public/
└── package.json
```

## How `axiosClient.js` Works

`axiosClient.js` is the single point of contact between the frontend and the backend. Instead of every service file configuring its own base URL and auth headers, they all import this one shared instance.

```js
// axiosClient.js
import axios from "axios";
import { getAuth } from "firebase/auth";

const axiosClient = axios.create({
  baseURL: "http://localhost:8000", // API Gateway URL
});

axiosClient.interceptors.request.use(async (config) => {
  const user = getAuth().currentUser;
  if (user) {
    const token = await user.getIdToken();
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

export default axiosClient;
```

**What it does:**

1. **Sets a single base URL** — `baseURL` points at the API Gateway, not at individual microservices. Every request from the frontend goes through the gateway, matching the architecture diagram (UI → API Gateway → downstream services). If you ever move the gateway (staging, prod, a different port), you change it in one place.

2. **Attaches the Firebase auth token automatically** — the request interceptor runs before every outgoing request. It grabs the currently signed-in Firebase user, requests a fresh ID token, and adds it as a `Bearer` token in the `Authorization` header. You never have to manually attach tokens in your components or service files.

3. **Centralizes future changes** — things like request timeouts, retry logic, error interceptors (e.g. auto-logout on a 401), or request logging only need to be added once, here, rather than in every service file.

### Why the per-service files exist

Each `xxxService.js` file (e.g. `eventService.js`, `venueService.js`) is a thin wrapper around `axiosClient` scoped to one backend microservice. This keeps components clean — they call `getEvent(id)` instead of writing raw axios calls with URLs scattered through the UI, and keeps each service file mapped 1:1 to a box in the ERD/architecture diagram.

### Usage Example

```jsx
// Inside a page or component
import { useEffect, useState } from "react";
import { getEvent } from "../api/eventService";

function EventDetailsPage({ eventId }) {
  const [event, setEvent] = useState(null);

  useEffect(() => {
    getEvent(eventId)
      .then((res) => setEvent(res.data))
      .catch((err) => console.error("Failed to load event:", err));
  }, [eventId]);

  if (!event) return <p>Loading...</p>;

  return <h1>{event.eventName}</h1>;
}
```

No token handling, no base URL, no header setup — `axiosClient` handles all of that behind the scenes. You only write the request logic that's specific to that endpoint.

### Adding a new endpoint

To call a new backend route:

1. Find (or create) the relevant `xxxService.js` file matching the microservice.
2. Add an exported function using `axiosClient`:
   ```js
   export const cancelEvent = (eventId) => axiosClient.delete(`/events/${eventId}`);
   ```
3. Import and use it in your component/page as shown above.

### Auth Context

`context/AuthContext.jsx` wraps the whole app and exposes the current Firebase user (`currentUser`), plus `login()` / `logout()` helpers. `axiosClient.js` reads from Firebase directly (`getAuth().currentUser`), so as long as the user is signed in via `AuthContext`, every API call is automatically authenticated — no extra wiring needed between the two.

---

# Backend

All business logic and database access lives here, in Python (FastAPI). Each microservice is an independent app with its own MySQL database, its own `Dockerfile`, and its own dependency list — none of them share code except through the `shared/` folder or by calling each other's HTTP APIs.

## File Structure

```
services/
│
├── api-gateway/                   # Single entry point for all frontend requests
│   ├── app/
│   │   ├── main.py                # FastAPI app instance, mounts routers
│   │   ├── routing/                # Forwards requests to the correct downstream service
│   │   ├── middleware/             # Verifies Firebase ID tokens on every request
│   │   └── core/config.py          # Env vars, service URLs
│   ├── requirements.txt
│   └── Dockerfile
│
├── user-service/                  # Owns: User DB
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/user.py         # /users endpoints
│   │   ├── models/user.py          # userId, userName, email, role (SQLAlchemy)
│   │   ├── schemas/user.py         # Pydantic request/response models
│   │   ├── services/               # profile logic, RBAC checks
│   │   ├── db/session.py           # MySQL connection/session
│   │   └── core/config.py
│   ├── alembic/                    # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
│
├── event-service/                 # Orchestrator. Owns: Event Info DB, Event Change DB
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/event.py        # /events endpoints
│   │   ├── models/
│   │   │   ├── event.py
│   │   │   └── event_change.py
│   │   ├── schemas/
│   │   ├── orchestration/          # Calls venue/equipment/registration/notification services
│   │   ├── db/session.py
│   │   └── core/config.py
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
├── venue-service/                 # Owns: Venue Info, Venue Booking
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/venue.py
│   │   ├── models/
│   │   │   ├── venue_info.py
│   │   │   └── venue_booking.py
│   │   ├── schemas/
│   │   ├── db/session.py
│   │   └── core/config.py
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
├── equipment-service/             # Owns: Equipment Info, equipment unit, equipment request
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/equipment.py
│   │   ├── models/
│   │   │   ├── equipment_info.py
│   │   │   ├── equipment_unit.py
│   │   │   └── equipment_request.py
│   │   ├── schemas/
│   │   ├── db/session.py
│   │   └── core/config.py
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
├── registration-service/          # Owns: Registration, Attendee Registration
│   ├── app/
│   │   ├── main.py
│   │   ├── routers/registration.py
│   │   ├── models/
│   │   │   ├── registration.py
│   │   │   └── attendee_registration.py
│   │   ├── schemas/
│   │   ├── db/session.py
│   │   └── core/config.py
│   ├── alembic/
│   ├── requirements.txt
│   └── Dockerfile
│
└── notification-service/          # No dedicated DB — sends emails/SMS/push
    ├── app/
    │   ├── main.py
    │   ├── routers/notification.py
    │   ├── services/                # Email/SMS/push sending logic
    │   └── core/config.py
    ├── requirements.txt
    └── Dockerfile
```

## Shared Backend Code

```
shared/
├── auth/               # Firebase ID token verification (used by api-gateway and/or each service)
├── schemas/            # Common Pydantic base models (e.g. pagination, error response shape)
├── exceptions/         # Shared custom exception classes
└── logging/            # Shared logging config
```

## Infra

```
infra/
├── docker-compose.yml   # Spins up every service + its own MySQL instance
└── mysql/
    └── init/            # Per-service init SQL scripts (schema creation)
```

## Every Service Follows the Same Internal Layout

To keep things predictable as the number of services grows:

| Folder | Purpose |
|---|---|
| `main.py` | Creates the FastAPI app, includes routers |
| `routers/` | Defines endpoints (URL paths, request handling) |
| `models/` | SQLAlchemy ORM models — one per table in that service's DB |
| `schemas/` | Pydantic models for validating requests/responses |
| `db/session.py` | Database engine/session setup for that service's MySQL DB |
| `core/config.py` | Environment variables, settings |
| `alembic/` | Database migration scripts |

## Request Flow Example — `getEvent(eventId)`

1. React calls `getEvent(123)` → `frontend/src/api/eventService.js`
2. Axios sends `GET /events/123` → **api-gateway** (verifies Firebase token)
3. Gateway forwards to **event-service** → `services/event-service/app/routers/event.py`
4. `event-service` queries the **Event Info DB** (MySQL) via `models/event.py`
5. Response flows back through the gateway → to axios → into React state

## Database-per-Service

Each microservice owns its own MySQL database — they do not query each other's tables directly. If `event-service` needs venue data, it calls `venue-service`'s HTTP API rather than joining across databases. This keeps services independently deployable and matches the grouped tables in the ERD (e.g. Venue Info + Venue Booking belong to `venue-service`; Registration + Attendee Registration belong to `registration-service`).
