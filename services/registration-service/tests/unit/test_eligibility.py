import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app.services.registration_service import eligibility
from tests.unit.support import confirmed_event


class FrozenClock(datetime):
    instant = datetime(2026, 9, 1, 12, 0, 0)

    @classmethod
    def utcnow(cls):
        return cls.instant


class TestEligibility(unittest.TestCase):
    def test_eligible_when_open_and_under_capacity(self):
        ok, reason = eligibility(confirmed_event(), 5)

        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_not_eligible_when_event_is_not_confirmed(self):
        ok, reason = eligibility(confirmed_event(status="submitted"), 0)

        self.assertFalse(ok)
        self.assertIn("confirmed", reason.lower())

    def test_not_eligible_when_registration_is_disabled(self):
        ok, reason = eligibility(confirmed_event(registrationEnabled=False), 0)

        self.assertFalse(ok)
        self.assertIn("enabled", reason.lower())

    def test_not_eligible_when_the_window_is_missing(self):
        ok, reason = eligibility(confirmed_event(registrationOpensAt=None, registrationClosesAt=None), 0)

        self.assertFalse(ok)
        self.assertIn("enabled", reason.lower())

    def test_not_eligible_before_registration_opens(self):
        opens = (datetime.utcnow() + timedelta(days=1)).isoformat() + "Z"
        ok, reason = eligibility(confirmed_event(registrationOpensAt=opens), 0)

        self.assertFalse(ok)
        self.assertIn("opens", reason.lower())

    def test_not_eligible_after_registration_closes(self):
        closes = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        ok, reason = eligibility(confirmed_event(registrationClosesAt=closes), 0)

        self.assertFalse(ok)
        self.assertIn("closed", reason.lower())

    def test_not_eligible_at_capacity(self):
        ok, reason = eligibility(confirmed_event(capacity=5), 5)

        self.assertFalse(ok)
        self.assertEqual(reason, "This event has reached capacity.")

    def test_one_place_below_capacity_is_still_open(self):
        ok, reason = eligibility(confirmed_event(capacity=5), 4)

        self.assertTrue(ok)
        self.assertIsNone(reason)

    def test_a_window_with_only_one_endpoint_is_closed(self):
        missing_open, open_reason = eligibility(confirmed_event(registrationOpensAt=None), 0)
        missing_close, close_reason = eligibility(confirmed_event(registrationClosesAt=None), 0)

        self.assertFalse(missing_open)
        self.assertEqual(open_reason, "Registration has not been enabled for this event.")
        self.assertFalse(missing_close)
        self.assertEqual(close_reason, "Registration has not been enabled for this event.")

    def test_the_open_and_close_instants_are_inclusive(self):
        now = FrozenClock.instant
        opened = confirmed_event(
            registrationOpensAt=now.isoformat(),
            registrationClosesAt=(now + timedelta(days=1)).isoformat(),
        )
        closing = confirmed_event(
            registrationOpensAt=(now - timedelta(days=1)).isoformat(),
            registrationClosesAt=now.isoformat(),
        )
        before = confirmed_event(
            registrationOpensAt=(now + timedelta(microseconds=1)).isoformat(),
            registrationClosesAt=(now + timedelta(days=1)).isoformat(),
        )
        after = confirmed_event(
            registrationOpensAt=(now - timedelta(days=1)).isoformat(),
            registrationClosesAt=(now - timedelta(microseconds=1)).isoformat(),
        )

        with patch("app.services.registration_service.datetime", FrozenClock):
            at_open, open_reason = eligibility(opened, 0)
            at_close, close_reason = eligibility(closing, 0)
            too_early, early_reason = eligibility(before, 0)
            too_late, late_reason = eligibility(after, 0)

        self.assertTrue(at_open)
        self.assertIsNone(open_reason)
        self.assertTrue(at_close)
        self.assertIsNone(close_reason)
        self.assertFalse(too_early)
        self.assertIn("opens", early_reason.lower())
        self.assertFalse(too_late)
        self.assertEqual(late_reason, "Registration has closed for this event.")
