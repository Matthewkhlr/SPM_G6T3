from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.services.registration_service import RegistrationService
from shared.testing.cases import ServiceTestCase
from tests.unit.support import confirmed_event, make_window


class TestRegistrationWithdrawal(ServiceTestCase):
    def setUp(self):
        super().setUp()
        make_window(self.db, capacity=2)
        self.service = RegistrationService(
            self.db, AttendeeRegistrationDAO(self.db), RegistrationWindowDAO(self.db)
        )
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(
                capacity=2,
                proposedStartAt=(datetime.utcnow() + timedelta(days=3)).isoformat(),
            ),
        )
        self.lookup.start()
        self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")

    def tearDown(self):
        self.lookup.stop()
        super().tearDown()

    def test_withdraw_keeps_the_row_and_releases_the_place(self):
        self.assertTrue(hasattr(self.service, "withdraw"), "withdraw is not implemented")

        row = self.service.withdraw("e1", "amy@example.com")
        summary = self.service.registration_summary("e1")

        self.assertEqual(row.status, "withdrawn")
        self.assertIsNotNone(self.db.get(type(row), row.attendeeRegistrationId))
        self.assertEqual(summary["registered"], 0)
        self.assertEqual(summary["withdrawn"], 1)
        self.assertEqual(summary["remaining"], 2)

    def test_withdraw_refuses_an_email_that_is_not_registered(self):
        self.assertTrue(hasattr(self.service, "withdraw"), "withdraw is not implemented")

        with self.assertRaises(HTTPException) as ctx:
            self.service.withdraw("e1", "nobody@example.com")

        self.assertIn(ctx.exception.status_code, (404, 409))

    def test_withdraw_refuses_an_event_that_has_already_started(self):
        self.assertTrue(hasattr(self.service, "withdraw"), "withdraw is not implemented")
        self.lookup.stop()
        started = confirmed_event(
            capacity=2,
            proposedStartAt=(datetime.utcnow() - timedelta(hours=1)).isoformat(),
        )
        self.lookup = patch("app.services.registration_service._event", return_value=started)
        self.lookup.start()

        with self.assertRaises(HTTPException) as ctx:
            self.service.withdraw("e1", "amy@example.com")

        self.assertEqual(ctx.exception.status_code, 409)

    def test_a_withdrawn_attendee_can_register_again(self):
        self.assertTrue(hasattr(self.service, "withdraw"), "withdraw is not implemented")

        self.service.withdraw("e1", "amy@example.com")
        again = self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")

        self.assertEqual(again.status, "registered")

    def test_summary_lists_withdrawn_rows_separately_from_registered_rows(self):
        self.assertTrue(
            hasattr(self.service, "list_registrations"),
            "list_registrations is not implemented",
        )
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")
        self.service.withdraw("e1", "amy@example.com")

        listed = self.service.list_registrations("e1", include_withdrawn=True)
        current = self.service.list_registrations("e1", include_withdrawn=False)

        self.assertEqual({row.attendeeEmail for row in listed}, {"amy@example.com", "ben@example.com"})
        self.assertEqual([row.attendeeEmail for row in current], ["ben@example.com"])

    def test_an_attendee_sees_only_their_own_registrations(self):
        self.assertTrue(
            hasattr(self.service, "list_for_attendee"),
            "list_for_attendee is not implemented",
        )
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")

        mine = self.service.list_for_attendee("amy@example.com")

        self.assertEqual([row.attendeeEmail for row in mine], ["amy@example.com"])
