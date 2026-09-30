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

From the repository root, `npm run test:unit` runs that suite for all six services. `.github/workflows/tests.yml` runs the same command on pushes to `dev` and `main`, and on pull requests into either branch. The job id is `test`, which is the status check to require on both branch rules. It only runs tests for functions that exist today.

## Not in the pipeline yet

These files live in `services/<service>/tests/upcoming/` and are not part of `npm run test:unit`. They fail until the function exists. Move a file back into `tests/unit/` once it passes, so the pipeline starts running it.

| File | Missing function |
|---|---|
| `event-service/tests/upcoming/test_event_lifecycle.py` | confirm, complete, cancel, change request, reschedule |
| `venue-service/tests/upcoming/test_venue_conflicts.py` | overlapping approval, unavailability, search |
| `registration-service/tests/upcoming/test_registration_withdrawal.py` | withdraw, summary, attendee list |
| `notification-service/tests/upcoming/test_notification_records.py` | record a notification |

Run one of them from the service directory with `python -m unittest discover -s tests/upcoming -p "test_*.py" -t .`

## Files

| Service | Unit files |
|---|---|
| user-service | `test_user_service.py`, `test_user_routes.py` |
| event-service | `test_event_schema.py`, `test_event_clients.py`, `test_event_service.py`, `test_event_drafts.py`, `test_event_listings.py`, `test_event_discard.py`, `test_event_decisions.py`, `test_event_routes.py` |
| venue-service | `test_venue_helpers.py`, `test_venue_catalogue.py`, `test_venue_bookings.py`, `test_venue_retirement.py`, `test_venue_routes.py`, `test_venue_layout_rules.py`, `test_venue_route_guards.py`, `test_venue_suitability.py`, `test_venue_suitability_routes.py`, `test_venue_booking_requests.py`, `test_venue_booking_request_routes.py` |
| equipment-service | `test_equipment_catalogue.py`, `test_equipment_units.py`, `test_equipment_reservations.py`, `test_equipment_requests.py`, `test_equipment_shortfalls.py`, `test_equipment_routes.py` |
| registration-service | `test_eligibility.py`, `test_event_lookup.py`, `test_registration_service.py`, `test_registration_routes.py` |
| notification-service | `test_notification_service.py`, `test_notification_routes.py` |

## Rules covered

| Service | Rules the unit files assert |
|---|---|
| user-service | First login links a Firebase uid by email. A later login resolves that uid. An unknown email or uid is 404. The directory lists every user. `GET /users/me` and `GET /users` return the public profile. |
| event-service | Create submits an event. Drafts can be saved, renamed, submitted, and discarded by the owning organiser. Another organiser is 403. A non-draft cannot be edited or discarded. Lists hide drafts, discarded events, or rejected events as each endpoint specifies. Approve and reject apply only to a submitted event, and reject stores the reason. Assigning a coordinator writes the assignment. Registration counts and identity lookups handle success, a non-200 response, and an unreachable service. End dates and registration windows must be in order. |
| venue-service | Capacity is the highest layout. Retired venues stay out of the default list and remain readable by id. Updates log layout, hours, facility, and field changes. An unchanged save does not add an update log. One confirmed upcoming booking blocks retire until `confirm` is true; several bookings are named in the 409. Approve and reject apply only while a booking is pending. A layout needs a name and a capacity of at least 1. Only Venue Staff can add, edit, or retire a venue. Suitability returns suitable, suitable with warnings, or not suitable with a reason per point: over capacity, an unsupported layout, a missing facility or accessibility feature, an overlapping confirmed booking or unavailability, or an event time outside opening hours (read in UTC; setup and teardown are not held to opening hours) fails; above 90% of capacity or an overlapping pending request warns. Touching bookings, the event's own bookings, and rejected bookings do not clash. Anything the request leaves out comes from the event record. A venue booking request is accepted only from the event's assigned coordinator while the event is approved or in planning; a failing venue is refused with its failures; warnings must be acknowledged and are stored with the request; the request carries the event's facts, the client organisation (its id if its name could not be loaded), and the coordinator's notes; an event has one pending request at a time; only the sender can withdraw a pending request, after which it no longer warns other events; Venue Staff are notified of each request and withdrawal, and an unreachable notification service does not undo the request. Requests list oldest first. |
| equipment-service | Create logs the opening quantity and rejects negative counts, counts above the total, and a duplicate code. Status follows unit rows: no units or available units are available; maintenance wins over damaged. A quantity cut that breaks a reservation is 409 until it is acknowledged. Availability subtracts only overlapping reservations, including timezone-aware times. An event check reports each requested line, a shortfall of one, out-of-service stock, and overlapping events. Touching periods do not compete. The check does not reserve, and a reservation above the serviceable quantity is 409. Releasing a reservation returns that quantity. Requests can be approved, rejected, and reserved once. A second reserve of the same request is 409. |
| registration-service | An attendee can register when the event is confirmed, the window is open, and capacity remains. A missing name, email, or window is 409. A closed, not-yet-open, disabled, unconfirmed, full, or duplicate registration is rejected. The event lookup forwards the bearer token and maps a failed call to 404. |
| notification-service | `POST /notifications` queues an email and returns channel, recipient, and `queued`. A notification row can be stored for the signed-in user. |
