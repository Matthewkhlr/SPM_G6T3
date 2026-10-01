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
| `POST /events/{id}/assign-coordinator` | `coordinator`; the assignee must also be a `coordinator` (422 otherwise) (SPM-66) |
| `GET /events/coordinators` | `coordinator` |
| `GET /events/{id}/coordinator` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` |
| `PATCH /events/{id}` | `coordinator` assigned to the event (SPM-71); not while it is completed, cancelled, rejected, a draft, or discarded |
| `GET /events/{id}/internal-notes` | `coordinator` |
| `GET /events/significant-fields` | signed-in caller |
| `GET /venues`, `GET /venues/{id}`, `GET /venues/{id}/activity-log` | `coordinator`, `venue`, `techsupport` |
| `POST /venues`, `PATCH /venues/{id}`, `POST /venues/{id}/retire` | `venue` |
| `POST /venues/suitability` | `coordinator`, `venue` |
| `POST /venues/bookings` | `coordinator` assigned to the event (SPM-63) |
| `GET /venues/bookings`, `GET /venues/bookings/{id}` | `coordinator`, `venue` |
| `POST /venues/bookings/{id}/withdraw` | `coordinator` who sent the request |
| `POST /venues/bookings/{id}/approve` or `/reject` | `venue` |
| `POST /venues/bookings/reverification` | `coordinator` (event-service calls it on a confirmed significant edit) |
| `POST /equipment/requests` | `coordinator` |
| `PATCH /equipment/requests/{id}/details` | `coordinator`, and only while the request is still pending |
| `POST /equipment/requests/{id}/review`, `/reserve`, or `/unavailable` | `techsupport` |
| `PATCH /equipment/requests/{id}` | refused |
| `POST /equipment/availability` with `eventId` | signed-in caller |
| `POST /equipment/reservations/{id}/release` | `techsupport` |
| `GET /equipment/reservations?eventId=` | `coordinator`, `techsupport` |
| `POST /equipment/reservations/reverification` | `coordinator` (event-service calls it on a confirmed significant edit) |

## Assigning a coordinator (SPM-66)

`GET /events/coordinators` lists every Event Coordinator as `{userId, name, email, activeEventCount}`. The count covers their assigned events that are not completed, cancelled, rejected, drafts, or discarded, and is for information only: there is no workload limit.

`POST /events/{id}/assign-coordinator` with `{"coordinatorId": "u6"}` assigns or reassigns the event. A `submitted` event moves to `under review`; other statuses are unchanged, and approve/reject accept `submitted` or `under review`. The assignment appears in `GET /events/{id}/activity-log` as a `kind: "assignment"` entry: `changedBy` assigned `newValue` (replacing `oldValue`) at `createdAt`. The new coordinator and the organiser are emailed through notification-service; that step is best effort, so a failed email does not undo the assignment. It returns 409 for completed, cancelled, rejected, draft, or discarded events, 422 when the assignee is not a coordinator, and 503 when user-service cannot be reached (nothing is saved then).

`GET /events/{id}/coordinator` returns `{coordinatorId, name, email}`, all null until someone is assigned. It is kept off `GET /events/{id}` so attendees never see it.

## Editing an event (SPM-71)

`PATCH /events/{id}` takes only the fields that change. Name, description, purpose, category, internal notes, and organiser contact save without a warning. Start, end, expected attendance, layout, accessibility needs, and equipment requirements are significant; `GET /events/significant-fields` lists both groups.

A significant change on an event with a confirmed (`approved`) venue booking or an `active`/`reserved` equipment reservation, or on a `confirmed` event, returns 409 and saves nothing:

```json
{
  "detail": {
    "message": "Changing expected attendance affects arrangements that are already in place. …",
    "requiresConfirmation": true,
    "significantFields": ["expectedAttendance"],
    "arrangements": [
      {"kind": "venue", "id": "vb-soon", "summary": "Venue booking at Marina Hall A, …"},
      {"kind": "equipment", "id": "er-e1", "summary": "Equipment reservation: 2 x Projector"}
    ],
    "statusChange": {"from": "confirmed", "to": "reconsidering"}
  }
}
```

Resend with `"confirmSignificantChange": true` to save. The affected booking and reservations get `needsReverification: true` and a `reverificationNote` naming the change. Their status is unchanged, so the venue and stock stay held. A `confirmed` event moves to `reconsidering`, and the response lists `flaggedArrangements`. If venue-service or equipment-service cannot be reached, the edit is refused with 503 and nothing is saved.

Every changed field is written to `GET /events/{id}/activity-log` as a `kind: "edit"` entry with `field`, `oldValue`, `newValue`, `changedBy`, and `createdAt`. Status changes stay `kind: "status"` entries. Internal notes are never on `GET /events/{id}`; coordinators read them from `GET /events/{id}/internal-notes`.

JSON is camelCase. Tables and conflict rules: [data-model.md](data-model.md). How to run the stack: [architecture.md](architecture.md). Acceptance tests: [testing/README.md](testing/README.md).
