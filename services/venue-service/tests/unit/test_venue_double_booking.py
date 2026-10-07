"""SPM-64: prevent double-booking of a venue."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Query

from app.main import app
from app.models.venue_unavailability import VenueUnavailability
from app.schemas.venue import EventFacts, OperatingHours, SuitabilityRequest, VenueUpdate
from app.services import occupancy
from app.services.venue_service import APPROVED_ELSEWHERE
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, END, START, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

MONDAY = datetime(2030, 1, 7)
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def at(hour, minute=0, day=MONDAY):
    return day + timedelta(hours=hour, minutes=minute)


class DoubleBookingCase(VenueCase):
    """Marina Hall A, open every day, with 30 minutes setup and 60 minutes
    turnaround. The first booking is Monday 10:00 to 12:00 UTC, so it occupies
    the hall from 09:30 to 13:00."""

    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(
            venue_create(operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS]),
            CALLER,
        )

    def request(self, starts_at, ends_at, event_id=None, venue=None):
        return self.service.create_booking(
            booking_create(
                (venue or self.hall).venueId, eventId=event_id or f"e-{uuid4().hex[:6]}", startsAt=starts_at, endsAt=ends_at
            ),
            "u-coord",
        )

    def approve(self, booking):
        return self.service.approve_booking(booking.bookingId, "u-venue", "OK")

    def confirmed(self, starts_at=at(10), ends_at=at(12), event_id="e-first"):
        return self.approve(self.request(starts_at, ends_at, event_id))

    def refused(self, booking):
        with self.assertRaises(HTTPException) as ctx:
            self.approve(booking)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.get_booking(booking.bookingId).status, "pending")
        return ctx.exception.detail

    def block(self, starts_at, ends_at, reason="Maintenance"):
        self.db.add(
            VenueUnavailability(
                unavailabilityId=str(uuid4()),
                venueId=self.hall.venueId,
                startsAt=starts_at,
                endsAt=ends_at,
                reason=reason,
                createdBy="u-venue",
            )
        )
        self.db.commit()


class TestOccupiedWindow(DoubleBookingCase):
    """AC2: the event start minus the venue's setup through the event end plus its turnaround."""

    def test_the_customers_own_example(self):
        self.assertEqual(occupancy.occupied_window(at(10), at(12), 30, 45), (at(9, 30), at(12, 45)))

    def test_a_request_and_its_approval_record_the_venues_window(self):
        booking = self.request(at(10), at(12))
        self.assertEqual((booking.setupStartsAt, booking.teardownEndsAt), (at(9, 30), at(13)))

        self.service.update_venue(self.hall.venueId, VenueUpdate(setupMinutes=45), CALLER)
        approved = self.approve(booking)

        self.assertEqual((approved.setupStartsAt, approved.teardownEndsAt), (at(9, 15), at(13)))


class TestOneSharedRule(DoubleBookingCase):
    """AC1: search, suitability and approval give the same answer for the same clash."""

    def test_search_suitability_and_approval_all_see_a_confirmed_booking(self):
        self.confirmed()
        competing = self.request(at(12, 30), at(14))
        event = EventFacts(expectedAttendance=10, proposedStartAt=at(12, 30), proposedEndAt=at(14))

        searched = self.service.search_venues(starts_at=at(12, 30), ends_at=at(14))
        verdict = self.service.check_suitability(
            SuitabilityRequest(eventId="e-second", venueId=self.hall.venueId), event
        ).verdict

        self.assertEqual(searched, [])
        self.assertEqual(verdict, "not suitable")
        self.refused(competing)

    def test_all_three_ask_the_shared_rule(self):
        event = EventFacts(expectedAttendance=10, proposedStartAt=at(10), proposedEndAt=at(12))
        booking = self.request(at(10), at(12))
        with patch.object(self.service, "commitments", wraps=self.service.commitments) as rule:
            self.service.search_venues(starts_at=at(10), ends_at=at(12))
            self.service.check_suitability(SuitabilityRequest(eventId="e-x", venueId=self.hall.venueId), event)
            self.approve(booking)

        self.assertEqual(rule.call_count, 3)


class TestConfirmedBookings(DoubleBookingCase):
    """AC3 and AC6: two confirmed bookings never overlap; windows that only touch are fine."""

    def test_a_second_overlapping_approval_is_refused_naming_the_clash(self):
        self.confirmed()

        detail = self.refused(self.request(at(11), at(13)))

        self.assertEqual(
            detail,
            "Marina Hall A is already confirmed for event e-first at an overlapping time (07 Jan 2030, 09:30 AM "
            "to 01:00 PM UTC, including setup and turnaround), so this request cannot be approved.",
        )

    def test_a_second_overlapping_approval_is_refused(self):
        """Moved from tests/upcoming now that the rule exists."""
        first = self.request(START, END, "e1")
        second = self.request(START + timedelta(hours=2), END + timedelta(hours=2), "e2")
        self.approve(first)

        self.refused(second)

    def test_overlap_boundaries(self):
        self.confirmed()
        cases = {
            "identical": (at(10), at(12)),
            "overlapping the start": (at(8), at(11)),
            "overlapping the end": (at(11), at(15)),
            "inside it": (at(10, 30), at(11, 30)),
            "containing it": (at(6), at(18)),
            "inside the setup": (at(7), at(9)),
            "inside the turnaround": (at(13), at(14)),
        }
        for name, (starts_at, ends_at) in cases.items():
            with self.subTest(name):
                self.refused(self.request(starts_at, ends_at))

    def test_event_times_that_only_touch_still_clash_once_setup_and_turnaround_are_added(self):
        self.confirmed()

        self.refused(self.request(at(12), at(13)))
        self.refused(self.request(at(8), at(10)))

    def test_occupied_windows_that_only_touch_do_not_clash(self):
        self.confirmed()

        # 13:30 to 14:00 is set up from 13:00; 07:00 to 08:30 is turned around by 09:30.
        after = self.approve(self.request(at(13, 30), at(14)))
        before = self.approve(self.request(at(7), at(8, 30)))

        self.assertEqual((after.status, before.status), ("approved", "approved"))

    def test_pending_rejected_and_other_venues_bookings_do_not_block_an_approval(self):
        other = self.service.create_venue(venue_create(name="Atrium"), CALLER)
        self.request(at(10), at(12))
        rejected = self.request(at(10), at(12))
        self.service.reject_booking(rejected.bookingId, "u-venue", "No")
        self.approve(self.request(at(10), at(12), venue=other))

        self.assertEqual(self.approve(self.request(at(10), at(12))).status, "approved")


class TestUnavailability(DoubleBookingCase):
    """AC4: a confirmed booking conflicts with an overlapping unavailability period."""

    def test_unavailability_overlapping_the_setup_blocks_the_approval_naming_it(self):
        self.block(at(9), at(9, 45))

        detail = self.refused(self.request(at(10), at(12)))

        self.assertEqual(
            detail,
            "Marina Hall A is unavailable from 07 Jan 2030, 09:00 AM to 09:45 AM UTC (Maintenance), "
            "so this request cannot be approved.",
        )

    def test_unavailability_without_a_reason_is_named_plainly(self):
        self.block(at(12, 30), at(14), reason="")

        self.assertEqual(
            self.refused(self.request(at(10), at(12))),
            "Marina Hall A is unavailable from 07 Jan 2030, 12:30 PM to 02:00 PM UTC, so this request cannot be approved.",
        )

    def test_unavailability_that_only_touches_the_window_does_not_block(self):
        self.block(at(8), at(9, 30))
        self.block(at(13), at(14))

        self.assertEqual(self.approve(self.request(at(10), at(12))).status, "approved")


class TestSimultaneousApprovals(DoubleBookingCase):
    """AC7: two approvals for clashing requests at once; exactly one succeeds."""

    def test_approval_reads_the_nearby_bookings_with_a_lock(self):
        booking = self.request(at(10), at(12))
        with patch.object(
            self.service.booking_dao,
            "find_event_times_overlapping",
            wraps=self.service.booking_dao.find_event_times_overlapping,
        ) as find:
            self.approve(booking)

        self.assertTrue(find.call_args.args[-1])

    def test_only_approval_asks_the_database_for_a_lock(self):
        """SQLite ignores row locks, so this checks they are asked for; the
        MySQL integration test checks what they do."""
        booking = self.request(at(10), at(12))
        with patch.object(Query, "with_for_update", autospec=True, side_effect=lambda query: query) as locked:
            self.service.search_venues(starts_at=at(10), ends_at=at(12))
            self.assertEqual(locked.call_count, 0)
            self.approve(booking)

        self.assertEqual(locked.call_count, 1)

    def test_when_the_database_refuses_the_overlap_the_loser_is_told_why(self):
        booking = self.request(at(10), at(12))
        refused = OperationalError("UPDATE venue_bookings", {}, MagicMock(args=(1644, "overlap")))

        with patch.object(self.service.db, "commit", side_effect=refused), patch.object(
            self.service.db, "rollback"
        ) as rollback, self.assertRaises(HTTPException) as ctx:
            self.approve(booking)

        self.assertEqual((ctx.exception.status_code, ctx.exception.detail), (409, APPROVED_ELSEWHERE))
        rollback.assert_called_once()

    def test_any_other_database_error_is_not_disguised_as_a_clash(self):
        booking = self.request(at(10), at(12))
        broken = OperationalError("UPDATE venue_bookings", {}, MagicMock(args=(2013, "lost connection")))

        with patch.object(self.service.db, "commit", side_effect=broken), patch.object(self.service.db, "rollback"):
            with self.assertRaises(OperationalError):
                self.approve(booking)


class TestReleasedBookingsFreeTheVenue(DoubleBookingCase):
    """AC8: once a booking stops holding the venue, the period is free again. Cancelling
    an event (SPM-114's release) and cancelling one booking (SPM-114) build the release;
    withdrawing is SPM-63's. This checks the shared rule then lets the period go."""

    def assert_free_again(self):
        self.assertEqual([row.name for row in self.service.search_venues(starts_at=at(10), ends_at=at(12))], ["Marina Hall A"])
        self.assertEqual(self.approve(self.request(at(10), at(12))).status, "approved")

    def test_cancelling_the_event_frees_its_confirmed_and_pending_bookings(self):
        self.confirmed(event_id="e-gone")
        self.request(at(10), at(12), event_id="e-gone")

        released = self.service.release_event_bookings("e-gone")

        self.assertEqual({row.status for row in released}, {"cancelled"})
        self.assert_free_again()

    def test_cancelling_one_booking_frees_its_period(self):
        held = self.confirmed(event_id="e-gone")

        self.service.cancel_booking(held.bookingId, {"userId": "u-venue", "role": "venue"}, None)

        self.assert_free_again()

    def test_withdrawing_a_pending_request_leaves_nothing_to_clash_with(self):
        waiting = self.request(at(10), at(12), event_id="e-gone")
        self.service.withdraw_booking(waiting.bookingId, {"userId": "u-coord"}, "u-coord")

        self.assertFalse(self.service.commitments(self.hall, at(10), at(12)).pending)
        self.assert_free_again()


class TestRoutes(DoubleBookingCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, role, path, body=None):
        with signed_in_as(role):
            return self.client.post(path, headers=HEADERS, json=body or {})

    def test_venue_staff_are_told_why_an_approval_is_refused(self):
        self.confirmed()
        competing = self.request(at(11), at(13))

        refused = self.post("venue", f"/venues/bookings/{competing.bookingId}/approve")

        self.assertEqual(refused.status_code, 409)
        self.assertIn("is already confirmed for event e-first", refused.json()["detail"])

