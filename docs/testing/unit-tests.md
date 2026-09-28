# Unit tests

Every service keeps its unittest files in `services/<service>/tests/unit/`. Split them by behaviour when a service has more than one area to cover. Shared setup for a service lives in `tests/unit/support.py`.

## Run

From `services/<service>`:

```bash
python -m pip install coverage
coverage run -m unittest discover -s tests/unit -p "test_*.py" -t .
coverage report
coverage html
```

`coverage report` must total 100% statement coverage. `coverage html` writes `htmlcov/index.html`.

Statement coverage only shows that a line ran. Boundary cases pin the comparison itself: the open and close instants of a registration window are inclusive, one place below capacity is accepted and the next is refused, a registration window that opens and closes at the same instant is refused, touching equipment reservations do not overlap, and a catalogue cut down to the reserved quantity is allowed. Each assertion states that result directly, so changing `<` to `<=` or `>` to `>=` fails the suite.

From the repository root, `npm run test:unit` runs that suite for all six services. GitHub Actions does the same on pull requests and on pushes to `main`.

`test_event_lifecycle.py`, `test_venue_conflicts.py`, `test_equipment_shortfalls.py`, `test_registration_withdrawal.py`, and `test_notification_records.py` describe rules whose functions are not written yet, so those cases fail until the functions exist. The other unit files pass, and the implemented `app/` code they exercise is at 100% statement coverage.

## Files

| Service | Unit files |
|---|---|
| user-service | `test_user_service.py`, `test_user_routes.py` |
| event-service | `test_event_schema.py`, `test_event_clients.py`, `test_event_service.py`, `test_event_drafts.py`, `test_event_listings.py`, `test_event_discard.py`, `test_event_decisions.py`, `test_event_routes.py`, `test_event_lifecycle.py` |
| venue-service | `test_venue_helpers.py`, `test_venue_catalogue.py`, `test_venue_bookings.py`, `test_venue_retirement.py`, `test_venue_routes.py`, `test_venue_conflicts.py` |
| equipment-service | `test_equipment_catalogue.py`, `test_equipment_units.py`, `test_equipment_reservations.py`, `test_equipment_requests.py`, `test_equipment_routes.py`, `test_equipment_shortfalls.py` |
| registration-service | `test_eligibility.py`, `test_event_lookup.py`, `test_registration_service.py`, `test_registration_routes.py`, `test_registration_withdrawal.py` |
| notification-service | `test_notification_service.py`, `test_notification_routes.py`, `test_notification_records.py` |

## Rules covered

| Service | Rules the unit files assert |
|---|---|
| user-service | First login links a Firebase uid by email. A later login resolves that uid. An unknown email or uid is 404. The directory lists every user. `GET /users/me` and `GET /users` return the public profile. |
| event-service | Create submits an event. Drafts can be saved, renamed, submitted, and discarded by the owning organiser. Another organiser is 403. A non-draft cannot be edited or discarded. Lists hide drafts, discarded events, or rejected events as each endpoint specifies. Approve and reject apply only to a submitted event, and reject stores the reason. Assigning a coordinator writes the assignment. Confirm, complete, cancel, change request, and reschedule follow the lifecycle rules. Registration counts and identity lookups handle success, a non-200 response, and an unreachable service. End dates and registration windows must be in order. |
| venue-service | Capacity is the highest layout. Retired venues stay out of the default list and remain readable by id. Updates log layout, hours, facility, and field changes. An unchanged save does not add an update log. One confirmed upcoming booking blocks retire until `confirm` is true; several bookings are named in the 409. Approve and reject apply only while a booking is pending. A second overlapping approval is refused. Unavailability blocks a booking in that period. Search filters by capacity and facility. Suitability fails when attendance exceeds the layout. |
| equipment-service | Create logs the opening quantity and rejects negative counts, counts above the total, and a duplicate code. Status follows unit rows: no units or available units are available; maintenance wins over damaged. A quantity cut that breaks a reservation is 409 until it is acknowledged. Availability subtracts only overlapping reservations, including timezone-aware times. A reserve above the serviceable quantity is refused. A shortfall names the line and does not reserve. Releasing a reservation returns the quantity. Requests can be approved, rejected, and reserved once. A second reserve of the same request is 409. |
| registration-service | An attendee can register when the event is confirmed, the window is open, and capacity remains. A missing name, email, or window is 409. A closed, not-yet-open, disabled, unconfirmed, full, or duplicate registration is rejected. Withdrawal keeps the row, releases the place, and allows the same attendee to register again. The summary separates withdrawn rows from registered rows. An attendee sees only their own registrations. The event lookup forwards the bearer token and maps a failed call to 404. |
| notification-service | `POST /notifications` queues an email and returns channel, recipient, and `queued`. A notification row can be stored for the signed-in user, including a recorded notification about an event. |
