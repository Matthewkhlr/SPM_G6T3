from unittest.mock import patch

from fastapi import HTTPException

from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.schemas.registration import AttendeeOut, RegisterRequest
from app.services.registration_service import RegistrationService
from shared.testing.cases import ServiceTestCase
from tests.unit.support import confirmed_event, make_window


class TestRegistrationService(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.service = RegistrationService(
            self.db, AttendeeRegistrationDAO(self.db), RegistrationWindowDAO(self.db)
        )
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(),
        )
        self.lookup.start()

    def tearDown(self):
        self.lookup.stop()
        super().tearDown()

    def test_session_dependency_closes_and_init_db_is_a_noop(self):
        self.close_db_dependency()

    def test_register_succeeds_when_the_event_is_open(self):
        make_window(self.db)

        row = self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-1")

        self.assertEqual(row.status, "registered")
        self.assertEqual(row.userId, "u-1")
        self.assertEqual(row.attendeeEmail, "amy@example.com")

    def test_register_without_a_window_conflicts(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e-no-window", "Amy Wong", "amy@example.com", user_id=None)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_register_rejects_a_missing_name(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e1", "", "amy@example.com", user_id=None)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_register_rejects_a_missing_email(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e1", "Amy Wong", "", user_id=None)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_register_conflicts_when_the_event_is_not_confirmed(self):
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(status="submitted"),
        )
        self.lookup.start()
        make_window(self.db)

        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e1", "Amy Wong", "amy@example.com", user_id=None)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_the_last_place_is_accepted_and_the_next_one_is_refused(self):
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(capacity=1),
        )
        self.lookup.start()
        make_window(self.db, capacity=1)

        first = self.service.register("e1", "Amy Wong", "amy@example.com", user_id=None)
        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e1", "Ben Tan", "ben@example.com", user_id=None)

        self.assertEqual(first.status, "registered")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail, "This event has reached capacity.")
        self.assertEqual(len(self.service.list_for_event("e1")), 1)

    def test_register_conflicts_on_a_duplicate_email(self):
        make_window(self.db)
        self.service.register("e1", "Amy Wong", "amy@example.com", user_id=None)

        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e1", "Amy Again", "AMY@example.com", user_id=None)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_list_for_event_returns_only_registered_rows(self):
        make_window(self.db)
        registered = self.service.register("e1", "Amy Wong", "amy@example.com", user_id=None)
        registered.status = "withdrawn"
        self.db.commit()

        self.assertEqual(self.service.list_for_event("e1"), [])

    def test_schema_models_round_trip_the_documented_fields(self):
        request = RegisterRequest(eventId="e1", name="Amy Wong", email="amy@example.com")
        attendee = AttendeeOut(
            attendeeRegistrationId="r1",
            eventId=request.eventId,
            attendeeName=request.name,
            attendeeEmail=request.email,
        )

        self.assertEqual(attendee.eventId, "e1")
