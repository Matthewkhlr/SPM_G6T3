from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.models.attendee_registration import AttendeeRegistration
from app.services.registration_service import RegistrationService, _registration_access
from shared.testing.cases import ServiceTestCase
from tests.unit.support import FakeEventClient, FakeResponse, make_window

OPENS = "2026-09-01T00:00:00"
CLOSES = "2026-10-01T00:00:00"


def access_payload(**overrides):
    payload = {
        "eventId": "e1",
        "registrationEnabled": True,
        "registrationOpensAt": OPENS,
        "registrationClosesAt": CLOSES,
        "capacity": 3,
    }
    payload.update(overrides)
    return payload


def add_attendee(db, event_id, email, name, status="registered", created_at=None):
    created = created_at or datetime.utcnow()
    row = AttendeeRegistration(
        attendeeRegistrationId=str(uuid4()),
        eventId=event_id,
        attendeeName=name,
        attendeeEmail=email,
        status=status,
        createdAt=created,
        withdrawnAt=created if status == "withdrawn" else None,
    )
    db.add(row)
    db.commit()
    return row


class TestRegistrationRoster(ServiceTestCase):
    def setUp(self):
        super().setUp()
        make_window(self.db, "e1", capacity=3)
        make_window(self.db, "e2", capacity=2)
        self.service = RegistrationService(
            self.db, AttendeeRegistrationDAO(self.db), RegistrationWindowDAO(self.db)
        )
        self.lookup = patch(
            "app.services.registration_service._registration_access",
            return_value=access_payload(),
        )
        self.lookup.start()

    def tearDown(self):
        self.lookup.stop()
        super().tearDown()

    def _replace_access(self, **overrides):
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._registration_access",
            return_value=access_payload(**overrides),
        )
        self.lookup.start()

    def test_the_list_is_limited_to_the_requested_event(self):
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        add_attendee(self.db, "e2", "venue@example.com", "Venue Ops", created_at=datetime.utcnow())

        roster = self.service.registration_roster("e1", "Bearer token")

        self.assertEqual([row.attendeeEmail for row in roster["attendees"]], ["amy@example.com"])
        self.assertNotIn("r-att-e2", {row.attendeeRegistrationId for row in roster["attendees"]})

    def test_each_row_shows_supplied_information_time_and_status(self):
        created = datetime(2026, 9, 20, 9, 30)
        registered = add_attendee(self.db, "e1", "amy@example.com", "Amy Wong", created_at=created)
        withdrawn = add_attendee(
            self.db,
            "e1",
            "ben@example.com",
            "Ben Tan",
            status="withdrawn",
            created_at=created + timedelta(hours=1),
        )

        roster = self.service.registration_roster("e1", "Bearer token")
        by_email = {row.attendeeEmail: row for row in roster["attendees"]}

        self.assertEqual(by_email["amy@example.com"].attendeeName, "Amy Wong")
        self.assertEqual(by_email["amy@example.com"].attendeeEmail, "amy@example.com")
        self.assertEqual(by_email["amy@example.com"].createdAt, registered.createdAt)
        self.assertEqual(by_email["amy@example.com"].status, "registered")
        self.assertEqual(by_email["ben@example.com"].status, "withdrawn")
        self.assertEqual(by_email["ben@example.com"].attendeeRegistrationId, withdrawn.attendeeRegistrationId)

    def test_summary_counts_and_remaining_places_treat_withdrawn_as_free(self):
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        add_attendee(self.db, "e1", "ben@example.com", "Ben Tan", status="withdrawn")

        roster = self.service.registration_roster("e1", "Bearer token")

        self.assertEqual(roster["capacity"], 3)
        self.assertEqual(roster["registered"], 1)
        self.assertEqual(roster["withdrawn"], 1)
        self.assertEqual(roster["remaining"], 2)

    def test_one_place_below_capacity_leaves_one_and_a_full_event_leaves_none(self):
        self._replace_access(capacity=2)
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        one_left = self.service.registration_roster("e1", "Bearer token")
        add_attendee(self.db, "e1", "ben@example.com", "Ben Tan")
        full = self.service.registration_roster("e1", "Bearer token")

        self.assertEqual(one_left["remaining"], 1)
        self.assertEqual(full["remaining"], 0)

    def test_remaining_stays_at_zero_when_registered_rows_exceed_capacity(self):
        self._replace_access(capacity=1)
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        add_attendee(self.db, "e1", "ben@example.com", "Ben Tan")

        roster = self.service.registration_roster("e1", "Bearer token")

        self.assertEqual(roster["registered"], 2)
        self.assertEqual(roster["remaining"], 0)

    def test_withdrawn_rows_can_be_filtered_out_without_changing_the_summary(self):
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        add_attendee(self.db, "e1", "ben@example.com", "Ben Tan", status="withdrawn")

        hidden = self.service.registration_roster("e1", "Bearer token", include_withdrawn=False)

        self.assertEqual([row.attendeeEmail for row in hidden["attendees"]], ["amy@example.com"])
        self.assertEqual(hidden["withdrawn"], 1)
        self.assertEqual(hidden["registered"], 1)

    def test_a_refused_caller_does_not_receive_the_rows(self):
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._registration_access",
            side_effect=HTTPException(status_code=403, detail="You do not have permission to view these registrations."),
        )
        self.lookup.start()

        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_roster("e1", "Bearer someone-else")

        self.assertEqual(ctx.exception.status_code, 403)

    def test_the_list_is_not_offered_when_registration_is_disabled(self):
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        self._replace_access(registrationEnabled=False)

        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_roster("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Registration has not been enabled for this event.")

    def test_an_empty_list_still_returns_capacity_and_the_registration_period(self):
        self._replace_access(capacity=50)

        roster = self.service.registration_roster("e1", "Bearer token")

        self.assertEqual(roster["attendees"], [])
        self.assertEqual(roster["capacity"], 50)
        self.assertEqual(roster["registered"], 0)
        self.assertEqual(roster["withdrawn"], 0)
        self.assertEqual(roster["remaining"], 50)
        self.assertEqual(roster["registrationOpensAt"], OPENS)
        self.assertEqual(roster["registrationClosesAt"], CLOSES)

    def test_registered_count_ignores_withdrawn_rows(self):
        add_attendee(self.db, "e1", "amy@example.com", "Amy Wong")
        add_attendee(self.db, "e1", "ben@example.com", "Ben Tan", status="withdrawn")

        self.assertEqual(self.service.registered_count("e1"), 1)
        self.assertEqual(self.service.registered_count("e-empty"), 0)


class TestRegistrationAccessLookup(ServiceTestCase):
    def setUp(self):
        super().setUp()
        FakeEventClient.response = FakeResponse(200, access_payload())
        FakeEventClient.error = None
        FakeEventClient.captured = {}

    def test_forwards_the_bearer_token(self):
        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            payload = _registration_access("e1", "Bearer some-real-token")

        self.assertEqual(payload["capacity"], 3)
        self.assertEqual(FakeEventClient.captured["headers"], {"Authorization": "Bearer some-real-token"})
        self.assertIn("/events/e1/registration-access", FakeEventClient.captured["url"])

    def test_sends_no_auth_header_when_none_is_available(self):
        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            _registration_access("e1", None)

        self.assertEqual(FakeEventClient.captured["headers"], {})

    def test_a_forbidden_event_response_stays_forbidden(self):
        FakeEventClient.response = FakeResponse(403, {"detail": "no"})

        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            with self.assertRaises(HTTPException) as ctx:
                _registration_access("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 403)

    def test_an_expired_token_stays_unauthorized(self):
        FakeEventClient.response = FakeResponse(401, {"detail": "Invalid or expired token"})

        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            with self.assertRaises(HTTPException) as ctx:
                _registration_access("e1", "Bearer expired-token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_any_other_failure_is_not_found(self):
        FakeEventClient.response = FakeResponse(404, {"detail": "Event not found"})

        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            with self.assertRaises(HTTPException) as ctx:
                _registration_access("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_an_unreachable_event_service_is_not_found(self):
        FakeEventClient.error = httpx.ConnectError("down")

        with patch("app.services.registration_service.httpx.Client", FakeEventClient):
            with self.assertRaises(HTTPException) as ctx:
                _registration_access("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 404)
