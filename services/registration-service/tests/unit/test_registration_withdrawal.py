from datetime import datetime, timedelta
from unittest.mock import patch
from uuid import uuid4

import httpx
from fastapi import HTTPException

from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.models.attendee_registration import AttendeeRegistration
from app.services.registration_service import RegistrationService
from shared.testing.cases import ServiceTestCase
from tests.unit.support import confirmed_event, make_window

INSTANT = datetime(2026, 10, 6, 9, 0, 0)


class FrozenClock(datetime):
    @classmethod
    def utcnow(cls):
        return INSTANT


class RecordingClient:
    calls = []

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json=None, headers=None):
        RecordingClient.calls.append({"url": url, "json": json, "headers": headers})
        return None


class FailingClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        raise httpx.ConnectError("notification service is down")

    def __exit__(self, *args):
        return False


class NotifyMustNotRun:
    def __init__(self, timeout):
        raise AssertionError("notification was sent for a refused withdrawal")


def future_start(**overrides):
    payload = confirmed_event(
        capacity=2,
        proposedStartAt=(datetime.utcnow() + timedelta(days=3)).isoformat(),
    )
    payload.update(overrides)
    return payload


class TestRegistrationWithdrawal(ServiceTestCase):
    def setUp(self):
        super().setUp()
        make_window(self.db, capacity=2)
        self.service = RegistrationService(
            self.db, AttendeeRegistrationDAO(self.db), RegistrationWindowDAO(self.db)
        )
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=future_start(),
        )
        self.notify = patch("app.services.registration_service.httpx.Client", RecordingClient)
        self.lookup.start()
        self.notify.start()
        RecordingClient.calls = []
        self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")

    def tearDown(self):
        self.notify.stop()
        self.lookup.stop()
        super().tearDown()

    def test_withdraw_keeps_the_row_and_releases_the_place(self):
        row = self.service.withdraw("e1", "amy@example.com")
        summary = self.service.registration_summary("e1")

        self.assertEqual(row.status, "withdrawn")
        self.assertIsNotNone(row.withdrawnAt)
        self.assertIsNotNone(self.db.get(type(row), row.attendeeRegistrationId))
        self.assertEqual(summary["registered"], 0)
        self.assertEqual(summary["withdrawn"], 1)
        self.assertEqual(summary["remaining"], 2)
        self.assertEqual(summary["remainingPlaces"], 2)
        self.assertEqual(summary["placesRemaining"], 2)

    def test_withdraw_matches_the_email_in_any_case(self):
        row = self.service.withdraw("e1", "AMY@EXAMPLE.COM")

        self.assertEqual(row.status, "withdrawn")
        self.assertEqual(row.attendeeEmail, "amy@example.com")

    def test_withdraw_refuses_an_email_that_is_not_registered(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.withdraw("e1", "nobody@example.com")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(self.service.registration_summary("e1")["registered"], 1)

    def test_a_second_withdraw_keeps_the_withdrawn_row(self):
        first = self.service.withdraw("e1", "amy@example.com")

        with self.assertRaises(HTTPException) as ctx:
            self.service.withdraw("e1", "amy@example.com")

        self.assertEqual(ctx.exception.status_code, 409)
        kept = self.db.get(type(first), first.attendeeRegistrationId)
        self.assertEqual(kept.status, "withdrawn")
        self.assertEqual(self.db.query(AttendeeRegistration).count(), 1)

    def test_withdraw_refuses_an_event_that_has_already_started(self):
        self.lookup.stop()
        started = future_start(proposedStartAt=(datetime.utcnow() - timedelta(hours=1)).isoformat())
        self.lookup = patch("app.services.registration_service._event", return_value=started)
        self.lookup.start()

        with patch("app.services.registration_service.httpx.Client", NotifyMustNotRun):
            with self.assertRaises(HTTPException) as ctx:
                self.service.withdraw("e1", "amy@example.com")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.list_for_attendee("amy@example.com")[0].status, "registered")

    def test_withdrawal_is_open_one_microsecond_before_the_start_and_closed_at_the_start(self):
        opens = (INSTANT - timedelta(days=1)).isoformat()
        closes = (INSTANT + timedelta(days=1)).isoformat()
        one_before = future_start(
            proposedStartAt=(INSTANT + timedelta(microseconds=1)).isoformat(),
            registrationOpensAt=opens,
            registrationClosesAt=closes,
        )
        at_start = future_start(
            proposedStartAt=INSTANT.isoformat(),
            registrationOpensAt=opens,
            registrationClosesAt=closes,
        )
        one_after = future_start(
            proposedStartAt=(INSTANT - timedelta(microseconds=1)).isoformat(),
            registrationOpensAt=opens,
            registrationClosesAt=closes,
        )

        with patch("app.services.registration_service.datetime", FrozenClock):
            with patch("app.services.registration_service._event", return_value=one_before):
                opened = self.service.withdraw("e1", "amy@example.com")
                self.assertEqual(opened.status, "withdrawn")
                self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")
            with patch("app.services.registration_service._event", return_value=at_start):
                with self.assertRaises(HTTPException) as at_ctx:
                    self.service.withdraw("e1", "amy@example.com")
            self.assertEqual(at_ctx.exception.status_code, 409)

            with patch("app.services.registration_service._event", return_value=one_after):
                with self.assertRaises(HTTPException) as after_ctx:
                    self.service.withdraw("e1", "amy@example.com")
            self.assertEqual(after_ctx.exception.status_code, 409)

        kept = self.service.list_registrations("e1", include_withdrawn=False)
        self.assertEqual([row.attendeeEmail for row in kept], ["amy@example.com"])

    def test_completed_or_cancelled_events_cannot_be_withdrawn_even_before_they_start(self):
        later = (INSTANT + timedelta(days=2)).isoformat()
        for status in ("completed", "cancelled", "Cancelled"):
            self.lookup.stop()
            self.lookup = patch(
                "app.services.registration_service._event",
                return_value=future_start(status=status, proposedStartAt=later),
            )
            self.lookup.start()
            with self.assertRaises(HTTPException) as ctx:
                self.service.withdraw("e1", "amy@example.com")
            self.assertEqual(ctx.exception.status_code, 409, status)

        self.assertEqual(self.service.list_for_attendee("amy@example.com")[0].status, "registered")

    def test_an_event_with_no_start_time_cannot_be_withdrawn(self):
        self.lookup.stop()
        event = future_start()
        event.pop("proposedStartAt")
        self.lookup = patch("app.services.registration_service._event", return_value=event)
        self.lookup.start()

        with self.assertRaises(HTTPException) as ctx:
            self.service.withdraw("e1", "amy@example.com")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIsNone(self.service.list_for_attendee("amy@example.com")[0].withdrawnAt)

    def test_withdrawing_one_of_two_registrations_releases_exactly_one_place(self):
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")
        self.assertEqual(self.service.registration_summary("e1")["remaining"], 0)

        self.service.withdraw("e1", "amy@example.com")
        summary = self.service.registration_summary("e1")

        self.assertEqual(summary["registered"], 1)
        self.assertEqual(summary["withdrawn"], 1)
        self.assertEqual(summary["remaining"], 1)
        self.assertEqual(summary["remainingPlaces"], summary["placesRemaining"])

    def test_a_withdrawn_place_stays_full_until_registered_drops_below_capacity(self):
        for email, user_id in (("ben@example.com", "u-ben"), ("cara@example.com", "u-cara")):
            self.db.add(
                AttendeeRegistration(
                    attendeeRegistrationId=str(uuid4()),
                    eventId="e1",
                    attendeeName=email,
                    attendeeEmail=email,
                    userId=user_id,
                    status="registered",
                    createdAt=datetime.utcnow(),
                )
            )
        self.db.commit()
        self.assertEqual(self.service.registration_summary("e1")["remaining"], 0)

        self.service.withdraw("e1", "cara@example.com")
        still_full = self.service.registration_summary("e1")
        self.assertEqual(still_full["registered"], 2)
        self.assertEqual(still_full["remaining"], 0)

        self.service.withdraw("e1", "ben@example.com")
        one_left = self.service.registration_summary("e1")
        self.assertEqual(one_left["registered"], 1)
        self.assertEqual(one_left["remaining"], 1)

    def test_a_missing_capacity_leaves_no_remaining_places(self):
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=future_start(capacity=None),
        )
        self.lookup.start()

        summary = self.service.registration_summary("e1")

        self.assertEqual(summary["capacity"], 0)
        self.assertEqual(summary["remaining"], 0)

    def test_a_withdrawn_attendee_can_register_again(self):
        withdrawn = self.service.withdraw("e1", "amy@example.com")
        again = self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")

        self.assertEqual(again.status, "registered")
        self.assertNotEqual(again.attendeeRegistrationId, withdrawn.attendeeRegistrationId)
        kept = self.db.get(type(withdrawn), withdrawn.attendeeRegistrationId)
        self.assertEqual(kept.status, "withdrawn")
        summary = self.service.registration_summary("e1")
        self.assertEqual(summary["registered"], 1)
        self.assertEqual(summary["withdrawn"], 1)
        self.assertEqual(summary["remaining"], 1)

    def test_reregister_is_allowed_at_the_close_instant_and_refused_one_microsecond_later(self):
        self.service.withdraw("e1", "amy@example.com")
        opens = (INSTANT - timedelta(days=1)).isoformat()
        start = (INSTANT + timedelta(days=2)).isoformat()
        at_close = future_start(
            proposedStartAt=start,
            registrationOpensAt=opens,
            registrationClosesAt=INSTANT.isoformat(),
        )
        after_close = future_start(
            proposedStartAt=start,
            registrationOpensAt=opens,
            registrationClosesAt=(INSTANT - timedelta(microseconds=1)).isoformat(),
        )

        with patch("app.services.registration_service.datetime", FrozenClock):
            with patch("app.services.registration_service._event", return_value=at_close):
                again = self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")
                self.assertEqual(again.status, "registered")
                self.service.withdraw("e1", "amy@example.com")

            with patch("app.services.registration_service._event", return_value=after_close):
                with self.assertRaises(HTTPException) as ctx:
                    self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")

        self.assertEqual(ctx.exception.status_code, 409)
        current = self.service.list_registrations("e1", include_withdrawn=False)
        self.assertEqual(current, [])

    def test_reregister_is_refused_once_the_released_place_has_been_taken(self):
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=future_start(capacity=1),
        )
        self.lookup.start()
        self.service.withdraw("e1", "amy@example.com")
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")

        with self.assertRaises(HTTPException) as ctx:
            self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.registration_summary("e1")["remaining"], 0)
        self.assertEqual(self.service.list_for_attendee("amy@example.com")[0].status, "withdrawn")

    def test_summary_lists_withdrawn_rows_separately_from_registered_rows(self):
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")
        self.service.withdraw("e1", "amy@example.com")

        listed = self.service.list_registrations("e1", include_withdrawn=True)
        current = self.service.list_registrations("e1", include_withdrawn=False)

        self.assertEqual({row.attendeeEmail for row in listed}, {"amy@example.com", "ben@example.com"})
        self.assertEqual([row.status for row in listed if row.attendeeEmail == "amy@example.com"], ["withdrawn"])
        self.assertEqual([row.attendeeEmail for row in current], ["ben@example.com"])

    def test_an_attendee_sees_only_their_own_registrations(self):
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")

        mine = self.service.list_for_attendee("AMY@example.com")

        self.assertEqual([row.attendeeEmail for row in mine], ["amy@example.com"])

    def test_owned_rows_follow_the_user_id_when_the_email_differs(self):
        self.db.add(
            AttendeeRegistration(
                attendeeRegistrationId="r-guest",
                eventId="e1",
                attendeeName="Guest",
                attendeeEmail="guest@example.com",
                userId="u-amy",
                status="registered",
                createdAt=datetime.utcnow(),
            )
        )
        self.db.commit()

        owned = self.service.list_owned("u-amy", "amy@example.com")
        by_user_only = self.service.list_owned("u-amy", None)
        by_email_only = self.service.list_owned(None, "GUEST@example.com")
        neither = self.service.list_owned(None, None)
        prefix = self.service.list_owned("u-a", "nobody@example.com")

        self.assertEqual(
            {row.attendeeEmail for row in owned},
            {"amy@example.com", "guest@example.com"},
        )
        self.assertEqual({row.attendeeEmail for row in by_user_only}, {"amy@example.com", "guest@example.com"})
        self.assertEqual([row.attendeeEmail for row in by_email_only], ["guest@example.com"])
        self.assertEqual(neither, [])
        self.assertEqual(prefix, [])

    def test_withdraw_for_caller_matches_user_id_or_email_and_refuses_everyone_else(self):
        row = self.service.list_for_attendee("amy@example.com")[0]
        by_user = self.service.get_for_caller(row.attendeeRegistrationId, {"userId": "u-amy", "email": "other@example.com"})
        self.assertEqual(by_user.attendeeRegistrationId, row.attendeeRegistrationId)

        withdrawn = self.service.withdraw_for_caller(
            row.attendeeRegistrationId,
            {"userId": "u-someone-else", "email": "Amy@Example.com"},
            authorization="Bearer token",
        )
        self.assertEqual(withdrawn.status, "withdrawn")

        with self.assertRaises(HTTPException) as again:
            self.service.withdraw_for_caller(
                row.attendeeRegistrationId,
                {"userId": "u-amy", "email": "amy@example.com"},
            )
        self.assertEqual(again.exception.status_code, 409)

        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-10")
        ben = self.service.list_for_attendee("ben@example.com")[0]
        with self.assertRaises(HTTPException) as prefix:
            self.service.withdraw_for_caller(ben.attendeeRegistrationId, {"userId": "u-1", "email": "no@example.com"})
        self.assertEqual(prefix.exception.status_code, 403)

        with self.assertRaises(HTTPException) as missing:
            self.service.withdraw_for_caller("missing", {"userId": "u-amy", "email": "amy@example.com"})
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(HTTPException) as anonymous:
            self.service.get_for_caller(ben.attendeeRegistrationId, {})
        self.assertEqual(anonymous.exception.status_code, 403)
        self.assertEqual(self.db.get(type(ben), ben.attendeeRegistrationId).status, "registered")

    def test_attendee_places_hide_names_and_increase_by_one_after_a_withdrawal(self):
        self.service.register("e1", "Ben Tan", "ben@example.com", user_id="u-ben")
        before = self.service.attendee_places("e1", "Bearer token")
        self.service.withdraw("e1", "amy@example.com")
        after = self.service.attendee_places("e1", "Bearer token")

        self.assertEqual(before["attendees"], [])
        self.assertNotIn("ben@example.com", str(before))
        self.assertEqual(after["remainingPlaces"], before["remainingPlaces"] + 1)
        self.assertEqual(after["placesRemaining"], after["remainingPlaces"])
        self.assertNotIn("amy@example.com", str(after))
        self.assertNotIn("ben@example.com", str(after))

    def test_attendee_places_are_not_offered_when_registration_is_disabled(self):
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=future_start(registrationEnabled=False),
        )
        self.lookup.start()

        with self.assertRaises(HTTPException) as ctx:
            self.service.attendee_places("e1", "Bearer token")

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertNotIn("amy@example.com", ctx.exception.detail)

    def test_notification_names_the_event_and_a_failure_does_not_undo_the_withdrawal(self):
        named = future_start(eventName="AI in Events Summit")
        unnamed = future_start()
        unnamed.pop("eventName", None)

        RecordingClient.calls = []
        with patch("app.services.registration_service._event", return_value=named):
            with patch("app.services.registration_service.httpx.Client", RecordingClient):
                named_row = self.service.withdraw("e1", "amy@example.com", authorization="Bearer token")
        record, email = RecordingClient.calls
        self.assertIn("/notifications/records", record["url"])
        self.assertIn("withdrawn", record["json"]["body"])
        self.assertIn("AI in Events Summit", record["json"]["body"])
        self.assertIn("e1", record["json"]["body"])
        self.assertEqual(record["headers"], {"Authorization": "Bearer token"})
        self.assertTrue(email["url"].endswith("/notifications"))
        self.assertEqual(email["json"]["to"], "amy@example.com")
        self.assertEqual(named_row.status, "withdrawn")

        self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")
        RecordingClient.calls = []
        with patch("app.services.registration_service._event", return_value=unnamed):
            with patch("app.services.registration_service.httpx.Client", RecordingClient):
                self.service.withdraw("e1", "amy@example.com")
        self.assertEqual(RecordingClient.calls[0]["headers"], {})
        self.assertIn("(e1)", RecordingClient.calls[0]["json"]["body"])

        self.service.register("e1", "Amy Wong", "amy@example.com", user_id="u-amy")
        with patch("app.services.registration_service.httpx.Client", FailingClient):
            failed = self.service.withdraw("e1", "amy@example.com")
        self.assertEqual(failed.status, "withdrawn")
        self.assertIsNotNone(self.db.get(type(failed), failed.attendeeRegistrationId))

    def test_the_organiser_roster_shows_the_withdrawal_and_the_released_place(self):
        access = {
            "eventId": "e1",
            "registrationEnabled": True,
            "registrationOpensAt": "2026-09-01T00:00:00",
            "registrationClosesAt": "2026-10-01T00:00:00",
            "capacity": 2,
        }
        self.service.withdraw("e1", "amy@example.com")
        with patch("app.services.registration_service._registration_access", return_value=access):
            roster = self.service.registration_roster("e1", "Bearer token", include_withdrawn=True)

        self.assertEqual(roster["attendees"][0].status, "withdrawn")
        self.assertEqual(roster["withdrawn"], 1)
        self.assertEqual(roster["registered"], 0)
        self.assertEqual(roster["remaining"], 2)
        self.assertEqual(roster["remainingPlaces"], 2)
