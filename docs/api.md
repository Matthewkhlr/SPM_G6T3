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
| `POST /events/{id}/approve` | `coordinator` assigned to the event (SPM-69); only while it is `under review` or `changes requested` |
| `GET /events/{id}/decision` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` |
| `GET /events/{id}/clarifications` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` (SPM-68) |
| `POST /events/{id}/clarifications`, `POST /events/{id}/clarifications/{cid}/resolve` | `coordinator` assigned to the event (SPM-68) |
| `POST /events/{id}/clarifications/{cid}/reply` | `organiser` of that event's organisation, or the assigned `coordinator` |
| `PATCH /events/{id}/registration-settings` | `coordinator` assigned to the event (SPM-90); from `planning` until `confirmed` |
| `GET /events/{id}/change-requests` | `organiser` of that event's organisation, `coordinator`, `venue`, `techsupport` (SPM-106) |
| `POST /events/{id}/change-requests` | `organiser` of that event's organisation (SPM-106) |
| `POST /events/{id}/change-requests/{crid}/withdraw` | the `organiser` who raised it |
| `POST /events/{id}/change-requests/{crid}/accept` or `/decline` | `coordinator` assigned to the event |
| `POST /notifications/records` with another user's `userId` | `coordinator`, `venue`, `techsupport` (anyone may name themselves) |
| `PATCH /events/{id}` | `coordinator` assigned to the event (SPM-71); not while it is completed, cancelled, rejected, a draft, or discarded |
| `GET /events/{id}/internal-notes` | `coordinator` |
| `GET /events/significant-fields` | signed-in caller |
| `GET /venues`, `GET /venues/{id}`, `GET /venues/{id}/activity-log` | `coordinator`, `venue`, `techsupport` |
| `POST /venues`, `PATCH /venues/{id}`, `POST /venues/{id}/retire` | `venue` |
| `GET /venues/search` | `coordinator`, `venue` (SPM-61) |
| `POST /venues/suitability` | `coordinator`, `venue` |
| `POST /venues/bookings` | `coordinator` assigned to the event (SPM-63) |
| `GET /venues/bookings`, `GET /venues/bookings/{id}` | `coordinator`, `venue` |
| `POST /venues/bookings/{id}/withdraw` | `coordinator` assigned to the event (SPM-46), so after a reassignment the new coordinator |
| `POST /venues/bookings/{id}/approve` or `/reject` | `venue`; approval is refused (409) when a confirmed booking or unavailability overlaps the occupied window (SPM-64) |
| `POST /venues/bookings/reverification` | `coordinator` (event-service calls it on a confirmed significant edit) |
| `POST /equipment/requests` | `coordinator` assigned to the event (SPM-46) |
| `PATCH /equipment/requests/{id}/details` | `coordinator` assigned to the event (SPM-46), and only while the request is still pending |
| `POST /equipment/requests/{id}/review`, `/reserve`, or `/unavailable` | `techsupport` |
| `PATCH /equipment/requests/{id}` | refused |
| `POST /equipment/availability` with `eventId` | signed-in caller |
| `POST /equipment/reservations/{id}/release` | `techsupport` |
| `GET /equipment/reservations?eventId=` | `coordinator`, `techsupport` |
| `POST /equipment/reservations/reverification` | `coordinator` (event-service calls it on a confirmed significant edit) |

## Assigning a coordinator (SPM-66)

`GET /events/coordinators` lists every Event Coordinator as `{userId, name, email, activeEventCount}`. The count covers their assigned events that are not completed, cancelled, rejected, drafts, or discarded, and is for information only: there is no workload limit.

`POST /events/{id}/assign-coordinator` with `{"coordinatorId": "u6"}` assigns or reassigns the event. A `submitted` event moves to `under review`; other statuses are unchanged. Reject accepts `submitted` or `under review`; approve needs an assigned coordinator (see SPM-69 below). The assignment appears in `GET /events/{id}/activity-log` as a `kind: "assignment"` entry: `changedBy` assigned `newValue` (replacing `oldValue`) at `createdAt`. The new coordinator and the organiser are emailed through notification-service; that step is best effort, so a failed email does not undo the assignment. It returns 409 for completed, cancelled, rejected, draft, or discarded events, 422 when the assignee is not a coordinator, and 503 when user-service cannot be reached (nothing is saved then).

`GET /events/{id}/coordinator` returns `{coordinatorId, name, email}`, all null until someone is assigned. It is kept off `GET /events/{id}` so attendees never see it.

## Approving a request (SPM-69)

`POST /events/{id}/approve` with `{"note": "Ready for planning"}` (the note is optional, up to 2000 characters, and shown to the organiser) moves an `under review` request to `planning`. Only the event's assigned coordinator can approve (403 for any other coordinator). A request with no coordinator, such as a `submitted` one, cannot be approved (409), and neither can one that is past review (409).

The decision is stored in `event_reviews` (`action: "approve"`, reviewer, note, time). The status change appears in `GET /events/{id}/activity-log` without the note, because attendees can read the log. The response is the event plus `decision`, `decisionNote`, `decidedBy`, and `decidedAt`. The organiser is emailed through notification-service. This is best effort, so a failed email does not undo the approval.

An event with an open clarification (`hasOpenClarifications: true`, see SPM-68 below) returns 409 and saves nothing until the coordinator confirms:

```json
{
  "detail": {
    "message": "This request still has open clarifications with the organiser. Confirm to approve it anyway.",
    "requiresConfirmation": true,
    "openClarifications": true
  }
}
```

Resend with `"confirmOpenClarifications": true` to approve.

Approval does not call venue-service or equipment-service, so no venue is booked and no equipment is reserved. Those arrangements stay outstanding.

`GET /events/{id}/decision` returns `{decision, decisionNote, decidedBy, decidedAt}`, all null until a decision is made. Like the coordinator's contact details, it is kept off `GET /events/{id}`, so attendees never see the note.

## Clarifications (SPM-68)

`POST /events/{id}/clarifications` with `{"message": "Please confirm expected attendance.", "field": "expectedAttendance"}` opens a clarification. `field` is optional and must be a field of an event request (422 otherwise), and the message cannot be blank. Only the assigned coordinator can raise one (403 for any other coordinator), and only while the request is `under review` or `changes requested`. A draft, an event with no coordinator, and an event past review are 409. The request moves to `changes requested` and the organiser is emailed (best effort). Several clarifications can be open at once, and each is open or resolved on its own.

`POST /events/{id}/clarifications/{cid}/reply` with `{"message": "Attendance stays at 80."}` adds to the thread (201). The organiser, a colleague in their organisation, or the assigned coordinator can reply; the other side is emailed. If the event has moved past review, the coordinator's email says so. A resolved clarification takes no more replies (409).

`POST /events/{id}/clarifications/{cid}/resolve` (assigned coordinator only) marks it resolved; resolving one twice is 409. When no clarification is left open, a `changes requested` request returns to `under review`. An event that has moved on keeps its status.

`GET /events/{id}/clarifications` lists every thread, oldest first, at any stage, including after the event is confirmed, completed, or cancelled. Organisers see them for their own organisation's events and staff for any event; attendees get 403. Each thread is returned as follows; `entries` holds the question, then every reply, oldest first:

```json
{
  "clarificationId": "rv-clarify-e3",
  "eventId": "e3",
  "message": "Please confirm expected attendance.",
  "field": "expectedAttendance",
  "status": "open",
  "raisedBy": "u2",
  "createdAt": "2026-10-01T09:00:00",
  "resolvedBy": null,
  "resolvedAt": null,
  "entries": [
    {"entryId": "rv-clarify-e3", "authorId": "u2", "authorName": "Ben Lee", "authorRole": "coordinator", "message": "Please confirm expected attendance.", "createdAt": "2026-10-01T09:00:00"},
    {"entryId": "…", "authorId": "u1", "authorName": "Alice Tan", "authorRole": "organiser", "message": "Attendance stays at 80.", "createdAt": "2026-10-01T11:30:00"}
  ]
}
```

`authorName` is null when user-service cannot be reached. Questions and replies are kept off `GET /events/{id}` and the activity log, which only record the status changes. Every event read includes `hasOpenClarifications`.

## Registration settings (SPM-90)

`PATCH /events/{id}/registration-settings` takes only the fields that change: `registrationEnabled`, `registrationOpensAt`, `registrationClosesAt`, and `capacity`. Only the assigned coordinator can use it (403 for any other coordinator, 409 with no coordinator). It works while the event is in planning, preparing, prepared, confirmed, or reconsidering; any other status is 409. Times with a UTC offset are stored as UTC, to the second. The period can be cleared with `null`; `registrationEnabled` and `capacity` cannot.

- Registration must close after it opens and no later than the event's start (422). This is checked whenever the request includes either period field.
- A `capacity` below the number currently registered is 409 and cannot be confirmed: `{"detail": {"message": "2 people are already registered, so the capacity cannot go below 2.", "registeredCount": 2}}`.
- The coordinator must confirm two situations: a `capacity` above what a confirmed venue booking holds in the event's layout, and turning registration off while attendees are registered. Until then the endpoint returns 409 and saves nothing. The response names both figures:

```json
{
  "detail": {
    "message": "A capacity of 500 is more than Marina Hall A holds in the Theatre layout (300). 2 attendees are already registered. Turning registration off will notify them.",
    "requiresConfirmation": true,
    "warnings": [
      {"kind": "venueCapacity", "capacity": 500, "venueCapacity": 300, "venueName": "Marina Hall A", "layout": "Theatre", "message": "…"},
      {"kind": "registrationOff", "registeredCount": 2, "message": "…"}
    ]
  }
}
```

Resend with `"confirmOverVenueCapacity": true` and/or `"confirmRegistrationOff": true` to save. A capacity sent unchanged is still checked against the booking and the registrations, because those can change on their own.

Each changed setting is written to `GET /events/{id}/activity-log` as a `kind: "edit"` entry. The organiser is emailed and gets an in-app notification (`event.registration_settings`) naming what changed. When registration is turned off, each registered attendee is emailed and, if they have an account, notified in-app (`registration.closed`). Their registrations stay in place, and `notifiedAttendees` in the response counts them. If registration-service or venue-service cannot be reached, the endpoint returns 503 and saves nothing. The settings are on every event read, and organisers see them on their event page.

## Change requests (SPM-106)

`GET /events/changeable-fields` lists what an organiser can ask to change: `eventName`, `description`, `purpose`, `category`, `proposedStartAt`, `proposedEndAt`, `expectedAttendance`, `layoutPreference`, `accessibilityNeeds`, `equipmentRequirements`.

`POST /events/{id}/change-requests` with `{"reason": "Client wants a dinner", "proposedChanges": {"layoutPreference": "Banquet"}}` raises a request (201). Who can raise one:

- The organiser who filed the event, or a colleague in their organisation, while it is under review (including `changes requested`), approved, in planning (including preparing and prepared), or confirmed (including `reconsidering`).
- Not for a draft (edited directly), a `submitted` request (no coordinator yet), or a completed, cancelled, or rejected event. These return 409.
- Not while another request is pending (409: withdraw it first).

The reason is required (422). Proposed values follow the same rules as `PATCH /events/{id}`, and other fields are 422. Only fields that actually differ are kept, and nothing to change is 422. The response includes `currentValues` alongside `proposedChanges`, plus `affectsVenue`, `affectsEquipment`, and `affectsRegistration`. The event itself is not touched, so its confirmed details still read as confirmed. The assigned coordinator is emailed.

`GET /events/{id}/change-requests` lists requests newest first. Organisers see them for their own organisation's events, staff for any event; attendees get 403.

- `POST …/{crid}/withdraw`: the organiser who raised a pending request takes it back (`withdrawn`). The coordinator is emailed.
- `POST …/{crid}/decline` with `{"reason": "Keep the original copy"}`: the assigned coordinator says no. The reason is required, and the event is unchanged.
- `POST …/{crid}/accept` with `{"reason": "", "confirmSignificantChange": false}`: the assigned coordinator applies the proposed values under the `PATCH /events/{id}` rules. A significant change on an event with confirmed arrangements, or on a confirmed event, returns the same 409 until `confirmSignificantChange` is true. Then the arrangements are flagged (listed in `flaggedArrangements`) and a confirmed event becomes `reconsidering`. Values that can no longer be applied are 422.

After accepting or declining, the organiser who raised the request is emailed and notified in-app (`event.change_request`), with the coordinator's reason. Closing a request that is no longer pending is 409. `reviewedBy` and `reviewedAt` say who closed it and when.

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
