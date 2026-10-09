"""SPM-116: place a tentative hold with an expiry."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from app.models.venue_unavailability import VenueUnavailability
from app.orchestration.clients import notify_coordinator
from app.schemas.venue import EventFacts, OperatingHours, SuitabilityRequest
from app.services import occupancy
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, COORDINATOR, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

MONDAY = datetime(2030, 1, 7)
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def at(hour, minute=0, day=MONDAY):
    return day + timedelta(hours=hour, minutes=minute)


class HoldCase(VenueCase):
    """Harbour Hall: open every day, 30 minutes setup and 45 minutes turnaround.
    Event A's request is 10:00 to 12:00 on 7 Jan 2030, so it occupies 09:30 to 12:45."""

    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(
            venue_create(
                name="Harbour Hall",
                setupMinutes=30,
                turnaroundMinutes=45,
                operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS],
            ),
            CALLER,
        )
        self.a = self.request("e-a", at(10), at(12))

    def request(self, event_id, starts_at, ends_at):
        return self.service.create_booking(
            booking_create(self.hall.venueId, eventId=event_id, startsAt=starts_at, endsAt=ends_at),
            "u-coord",
            event_snapshot={"eventName": f"Event {event_id}"},
        ).bookingId

    def hold(self, booking_id, expires_at=None):
        return self.service.place_hold(booking_id, expires_at or at(8, day=MONDAY - timedelta(days=3)), CALLER)

    def refused(self, call, status):
        with self.assertRaises(HTTPException) as ctx:
            call()
        self.assertEqual(ctx.exception.status_code, status)
        return ctx.exception.detail

    def expire(self, booking_id):
        """Hold expiry is checked against the clock, so wind this hold's expiry back."""
        row = self.db.get(VenueBooking, booking_id)
        row.holdExpiresAt = datetime.utcnow() - timedelta(minutes=1)
        self.db.commit()

    def free(self, starts_at, ends_at, event_id="e-other"):
        rows = self.service.search_venues(starts_at=starts_at, ends_at=ends_at, exclude_event_id=event_id)
        return self.hall.venueId in [row.venueId for row in rows]


class TestPlacingAHold(HoldCase):
    """AC1: Venue Staff place a hold with a required expiry in the future."""

    def test_a_pending_request_is_held_until_the_expiry_given(self):
        before = datetime.utcnow()
        held = self.hold(self.a, at(17, day=MONDAY - timedelta(days=3)))

        self.assertEqual(held.hold.state, "active")
        self.assertEqual(held.hold.expiresAt, at(17, day=MONDAY - timedelta(days=3)))
        self.assertEqual(held.hold.placedBy, CALLER["userId"])
        self.assertGreaterEqual(held.hold.placedAt, before)
        self.assertEqual(held.status, "pending")
        stored = self.db.get(VenueBooking, self.a)
        self.assertEqual((stored.holdExpiresAt, stored.holdEndedAt), (at(17, day=MONDAY - timedelta(days=3)), None))

    def test_an_expiry_with_a_timezone_is_stored_in_utc(self):
        plus_eight = timezone(timedelta(hours=8))

        held = self.hold(self.a, datetime(2030, 1, 6, 9, 0, tzinfo=plus_eight))

        self.assertEqual(held.hold.expiresAt, datetime(2030, 1, 6, 1, 0))

    def test_an_expiry_in_the_past_or_right_now_is_refused(self):
        for expires_at in (datetime.utcnow() - timedelta(days=1), datetime.utcnow() - timedelta(seconds=1)):
            with self.subTest(expires_at=expires_at):
                detail = self.refused(lambda: self.hold(self.a, expires_at), 422)
                self.assertEqual(detail, "The hold must expire at a future date and time.")
        self.assertIsNone(self.service.get_booking(self.a).hold)

    def test_an_expiry_a_minute_ahead_is_accepted(self):
        self.assertEqual(self.hold(self.a, datetime.utcnow() + timedelta(minutes=1)).hold.state, "active")

    def test_the_expiry_may_be_the_events_start_but_not_later(self):
        detail = self.refused(lambda: self.hold(self.a, at(10, 1)), 422)
        self.assertEqual(detail, "The hold must expire no later than the event's start (07 Jan 2030, 10:00 AM UTC).")

        self.assertEqual(self.hold(self.a, at(10)).hold.expiresAt, at(10))

    def test_only_a_pending_request_can_be_held(self):
        approved, rejected = self.request("e-b", at(15), at(16)), self.request("e-c", at(18), at(19))
        withdrawn = self.request("e-d", at(21), at(22))
        self.service.approve_booking(approved, "u-venue", None)
        self.service.reject_booking(rejected, "u-venue", "No")
        self.service.withdraw_booking(withdrawn, COORDINATOR, COORDINATOR["userId"])

        for booking_id, status in ((approved, "approved"), (rejected, "rejected"), (withdrawn, "withdrawn")):
            with self.subTest(status=status):
                self.assertEqual(
                    self.refused(lambda: self.hold(booking_id), 409),
                    f"Only a pending booking request can be held. This request is already {status}.",
                )

    def test_a_request_already_held_cannot_be_held_again(self):
        self.hold(self.a)

        detail = self.refused(lambda: self.hold(self.a, at(9, day=MONDAY - timedelta(days=1))), 409)

        self.assertEqual(
            detail,
            "This request is already held until 04 Jan 2030, 08:00 AM UTC. Release that hold first to set a new expiry.",
        )

    def test_a_released_or_expired_hold_can_be_placed_again(self):
        self.hold(self.a)
        self.service.release_hold(self.a)
        self.assertEqual(self.hold(self.a).hold.state, "active")

        self.expire(self.a)
        again = self.hold(self.a, at(12, day=MONDAY - timedelta(days=2)))

        self.assertEqual((again.hold.state, again.hold.expiresAt), ("active", at(12, day=MONDAY - timedelta(days=2))))
        self.assertIsNone(self.db.get(VenueBooking, self.a).holdEndReason)

    def test_an_unknown_request_is_not_found(self):
        self.assertEqual(self.refused(lambda: self.hold("nope"), 404), "Venue booking not found")

    def test_a_venue_already_taken_for_the_window_cannot_be_held(self):
        confirmed = self.request("e-b", at(12), at(13))  # set up from 11:30, inside A's window
        self.service.approve_booking(confirmed, "u-venue", None)

        detail = self.refused(lambda: self.hold(self.a), 409)

        self.assertEqual(
            detail,
            'Harbour Hall is already confirmed for "Event e-b" at an overlapping time '
            "(07 Jan 2030, 11:30 AM to 01:45 PM UTC, including setup and turnaround), so this request cannot be held.",
        )

    def test_two_holds_never_overlap(self):
        b = self.request("e-b", at(12), at(13))
        self.hold(self.a)

        detail = self.refused(lambda: self.hold(b), 409)

        self.assertIn('Harbour Hall is on a tentative hold until 04 Jan 2030, 08:00 AM UTC for "Event e-a"', detail)
        self.assertTrue(detail.endswith("so this request cannot be held."))

    def test_unavailability_overlapping_the_window_blocks_a_hold(self):
        self.db.add(
            VenueUnavailability(
                unavailabilityId="u-1",
                venueId=self.hall.venueId,
                startsAt=at(12, 30),
                endsAt=at(14),
                reason="Maintenance",
                createdBy="u-venue",
            )
        )
        self.db.commit()

        detail = self.refused(lambda: self.hold(self.a), 409)

        self.assertEqual(
            detail,
            "Harbour Hall is unavailable from 07 Jan 2030, 12:30 PM to 02:00 PM UTC (Maintenance), "
            "so this request cannot be held.",
        )

    def test_another_pending_request_or_a_touching_window_does_not_stop_a_hold(self):
        self.request("e-b", at(11), at(12))  # pending only: it waits for a decision
        touching = self.request("e-c", at(13, 15), at(14))  # set up from 12:45, as A's window ends
        self.service.approve_booking(touching, "u-venue", None)

        self.assertEqual(self.hold(self.a).hold.state, "active")


class TestAnActiveHoldReservesTheVenue(HoldCase):
    """AC2: until it expires or is released, nobody else can have the window."""

    def setUp(self):
        super().setUp()
        self.hold(self.a)

    def test_search_leaves_the_venue_out_for_any_overlapping_period(self):
        self.assertFalse(self.free(at(12), at(13)))  # set up from 11:30, inside A's 09:30 to 12:45
        self.assertTrue(self.free(at(13, 15), at(14)))  # set up from 12:45: windows only touch

    def test_the_held_event_itself_still_finds_the_venue(self):
        self.assertTrue(self.free(at(10), at(12), event_id="e-a"))

    def test_suitability_fails_naming_the_hold_and_its_expiry(self):
        result = self.service.check_suitability(
            SuitabilityRequest(eventId="e-b", venueId=self.hall.venueId, startsAt=at(12), endsAt=at(13)),
            EventFacts(expectedAttendance=10),
        )

        self.assertEqual(result.verdict, "not suitable")
        # The held request is reported once, as the hold, not again as an ordinary pending request.
        self.assertEqual(
            [(reason.check, reason.message) for reason in result.reasons],
            [
                (
                    "hold",
                    'This venue is on a tentative hold for "Event e-a" until 04 Jan 2030, 08:00 AM UTC, at an '
                    "overlapping time (07 Jan 2030, 09:30 AM to 12:45 PM UTC, including setup and turnaround).",
                )
            ],
        )

    def test_another_events_request_cannot_be_approved_while_the_hold_lasts(self):
        b = self.request("e-b", at(12), at(13))

        detail = self.refused(lambda: self.service.approve_booking(b, "u-venue", None), 409)

        self.assertIn("is on a tentative hold until 04 Jan 2030, 08:00 AM UTC", detail)
        self.assertEqual(self.service.get_booking(b).status, "pending")

    def test_the_held_request_itself_can_be_approved_and_its_hold_becomes_the_booking(self):
        approved = self.service.approve_booking(self.a, "u-venue", None)

        self.assertEqual((approved.status, approved.hold.state), ("approved", "approved"))
        self.assertFalse(self.free(at(12), at(13)))  # now held by the confirmed booking

    def test_a_held_request_leaves_the_venue_out_where_an_ordinary_one_only_marks_it_contested(self):
        self.request("e-b", at(20), at(21))  # an ordinary pending request later that day

        later = self.service.search_venues(starts_at=at(20), ends_at=at(21), exclude_event_id="e-x")
        during = self.service.search_venues(starts_at=at(10), ends_at=at(12), exclude_event_id="e-x")

        self.assertEqual([row.contested for row in later], [True])
        self.assertEqual(during, [])

    def test_releasing_the_hold_frees_the_venue(self):
        released = self.service.release_hold(self.a)

        self.assertEqual(released.hold.state, "released")
        self.assertTrue(self.free(at(12), at(13)))
        b = self.request("e-b", at(12), at(13))
        self.assertEqual(self.service.approve_booking(b, "u-venue", None).status, "approved")

    def test_only_an_active_hold_can_be_released(self):
        self.service.release_hold(self.a)
        never_held = self.request("e-b", at(20), at(21))

        for booking_id in (self.a, never_held):
            with self.subTest(booking_id=booking_id):
                self.assertEqual(
                    self.refused(lambda: self.service.release_hold(booking_id), 409),
                    "This request has no active hold to release.",
                )
        self.assertEqual(self.refused(lambda: self.service.release_hold("nope"), 404), "Venue booking not found")


class TestAnExpiredHold(HoldCase):
    """AC3 and AC4: an expired hold reserves nothing and is not a confirmed booking."""

    def setUp(self):
        super().setUp()
        self.hold(self.a)
        self.expire(self.a)

    def test_it_is_reported_as_expired_and_the_request_is_still_only_pending(self):
        booking = self.service.get_booking(self.a)

        self.assertEqual((booking.status, booking.hold.state), ("pending", "expired"))
        self.assertEqual(self.service.list_bookings("approved", None, self.hall.venueId), [])

    def test_the_venue_is_available_again_for_that_period(self):
        self.assertTrue(self.free(at(12), at(13)))
        b = self.request("e-b", at(12), at(13))
        self.assertEqual(self.service.approve_booking(b, "u-venue", None).status, "approved")

    def test_its_request_only_warns_like_any_pending_request(self):
        result = self.service.check_suitability(
            SuitabilityRequest(eventId="e-b", venueId=self.hall.venueId, startsAt=at(12), endsAt=at(13)),
            EventFacts(expectedAttendance=10),
        )

        self.assertEqual(result.verdict, "suitable with warnings")
        self.assertEqual([reason.check for reason in result.reasons], ["pendingRequest"])

    def test_ending_its_request_leaves_it_recorded_as_expired(self):
        self.assertEqual(self.service.reject_booking(self.a, "u-venue", "Too late").hold.state, "expired")
        self.assertIsNone(self.db.get(VenueBooking, self.a).holdEndReason)


class TestHoldStateBoundary(HoldCase):
    def test_a_hold_is_active_until_the_exact_expiry_time(self):
        row = VenueBooking(status="pending", holdExpiresAt=at(8))

        self.assertEqual(occupancy.hold_state(row, at(7, 59)), "active")
        self.assertEqual(occupancy.hold_state(row, at(8)), "expired")
        self.assertIsNone(occupancy.hold_state(VenueBooking(status="pending"), at(8)))


class TestTheHoldEndsWithItsRequest(HoldCase):
    """AC6, and the other ways a request ends."""

    def setUp(self):
        super().setUp()
        self.hold(self.a)

    def test_rejecting_the_request_releases_its_hold(self):
        rejected = self.service.reject_booking(self.a, "u-venue", "Not suitable")

        self.assertEqual((rejected.status, rejected.hold.state), ("rejected", "rejected"))
        self.assertTrue(self.free(at(12), at(13)))

    def test_withdrawing_or_cancelling_the_event_ends_the_hold(self):
        withdrawn = self.service.withdraw_booking(self.a, COORDINATOR, COORDINATOR["userId"])
        self.assertEqual(withdrawn.hold.state, "withdrawn")

        b = self.request("e-b", at(12), at(13))
        self.hold(b)
        (released,) = self.service.release_event_bookings("e-b")
        self.assertEqual((released.status, released.hold.state), ("cancelled", "cancelled"))
        self.assertTrue(self.free(at(12), at(13)))


class TestHoldRoutes(HoldCase):
    EVENT = EventFacts(eventName="AI Summit", coordinatorId="u-coord", status="planning")

    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, path, role="venue", json=None, event=EVENT):
        with signed_in_as(role), patch("app.routers.venue.fetch_event_facts", return_value=event), patch(
            "app.routers.venue.notify_coordinator", return_value=True
        ) as notify:
            response = self.client.post(f"/venues/bookings/{self.a}{path}", headers=HEADERS, json=json)
        return response, notify

    def test_venue_staff_hold_a_request_and_the_coordinator_is_told_until_when(self):
        held, notify = self.post("/hold", json={"expiresAt": "2030-01-04T08:00:00Z"})

        self.assertEqual(held.status_code, 200)
        self.assertEqual(held.json()["hold"]["state"], "active")
        self.assertEqual(held.json()["hold"]["expiresAt"], "2030-01-04T08:00:00")
        notify.assert_called_once_with(
            "u-coord",
            "e-a",
            "Venue on hold for your event",
            'Harbour Hall is on a tentative hold for "AI Summit" until 04 Jan 2030, 08:00 AM UTC. If the request '
            "is not approved by then, the hold expires and the venue becomes available to other requests.",
            HEADERS["Authorization"],
        )

    def test_an_event_without_a_coordinator_tells_nobody(self):
        held, notify = self.post("/hold", json={"expiresAt": "2030-01-04T08:00:00Z"}, event=EventFacts())

        self.assertEqual(held.status_code, 200)
        notify.assert_not_called()

    def test_a_refused_hold_tells_nobody(self):
        refused, notify = self.post("/hold", json={"expiresAt": "2020-01-04T08:00:00Z"})

        self.assertEqual((refused.status_code, refused.json()["detail"]), (422, "The hold must expire at a future date and time."))
        notify.assert_not_called()

    def test_an_expiry_is_required(self):
        self.assertEqual(self.post("/hold", json={})[0].status_code, 422)

    def test_venue_staff_release_a_hold(self):
        self.post("/hold", json={"expiresAt": "2030-01-04T08:00:00Z"})

        released, _ = self.post("/hold/release")

        self.assertEqual((released.status_code, released.json()["hold"]["state"]), (200, "released"))

    def test_only_venue_staff_can_hold_or_release(self):
        for role in ("coordinator", "organiser", "techsupport", "safety", "attendee"):
            for path in ("/hold", "/hold/release"):
                with self.subTest(role=role, path=path):
                    response, _ = self.post(path, role=role, json={"expiresAt": "2030-01-04T08:00:00Z"})
                    self.assertEqual(response.status_code, 403)

    def test_a_booking_reply_shows_no_hold_until_one_is_placed(self):
        with signed_in_as("venue"):
            booking = self.client.get(f"/venues/bookings/{self.a}", headers=HEADERS).json()

        self.assertIsNone(booking["hold"])


class TestNotifyingTheCoordinator(VenueCase):
    def reply(self, status_code):
        return MagicMock(status_code=status_code)

    def test_the_notice_goes_to_the_coordinators_inbox(self):
        with patch("app.orchestration.clients.httpx.post", return_value=self.reply(201)) as post:
            sent = notify_coordinator("u-coord", "e1", "Title", "Body", "Bearer t")

        self.assertTrue(sent)
        self.assertTrue(post.call_args.args[0].endswith("/notifications/records"))
        self.assertEqual(
            post.call_args.kwargs["json"],
            {"userId": "u-coord", "eventId": "e1", "type": "venue.hold", "title": "Title", "body": "Body"},
        )
        self.assertEqual(post.call_args.kwargs["headers"], {"Authorization": "Bearer t"})

    def test_a_refused_or_unreachable_notification_is_logged_not_raised(self):
        with patch("app.orchestration.clients.httpx.post", return_value=self.reply(403)):
            self.assertFalse(notify_coordinator("u-coord", "e1", "Title", "Body", "Bearer t"))
        with patch("app.orchestration.clients.httpx.post", side_effect=httpx.ConnectError("down")):
            self.assertFalse(notify_coordinator("u-coord", "e1", "Title", "Body", "Bearer t"))
