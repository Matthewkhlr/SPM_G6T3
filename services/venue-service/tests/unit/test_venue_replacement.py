"""SPM-115: replace an approved booking after its venue is blocked.

Recording the block does not change the booking or the event. The assigned
coordinator searches for another venue and requests it. That request is checked
on its own. Only then is the original booking cancelled, and it stays readable.
"""

from datetime import datetime, timedelta

from fastapi import HTTPException

from app.schemas.venue import EventFacts, Layout, OperatingHours, ReplacementRequest, UnavailabilityCreate, VenueBookingCreate
from tests.unit.support import CALLER, COORDINATOR, VenueCase, venue_create

MONDAY = datetime(2030, 1, 7)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
OTHER = {"userId": "u-other", "userName": "Cara", "role": "coordinator"}


def at(hour, day=MONDAY):
    return day + timedelta(hours=hour)


class ReplacementCase(VenueCase):
    def setUp(self):
        super().setUp()
        self.venue = self.venue_named("Marina Hall A", "MH-A")
        self.other = self.venue_named("Exhibition Hall B", "EH-B")
        self.event = EventFacts(
            eventName="AI Summit",
            status="planning",
            coordinatorId=COORDINATOR["userId"],
            organisationId="org-1",
            organisationName="Apex Partners",
            expectedAttendance=10,
            layoutPreference="Theatre",
            accessibilityNeeds="Wheelchair access required.",
            venueRequirements="Stage and PA system.",
            proposedStartAt=at(10),
            proposedEndAt=at(12),
        )

    def venue_named(self, name, code):
        return self.service.create_venue(
            venue_create(
                name=name,
                code=code,
                layouts=[Layout(name="Theatre", capacity=100), Layout(name="Boardroom", capacity=20)],
                operatingHours=[OperatingHours(day=day, opens="08:00", closes="18:00") for day in WEEKDAYS],
            ),
            CALLER,
        )

    def request(self, venue_id, event_id="e-mine"):
        return self.service.request_booking(
            VenueBookingCreate(venueId=venue_id, eventId=event_id, startsAt=at(10), endsAt=at(12)),
            COORDINATOR,
            self.event,
        )

    def approve(self, venue_id, event_id="e-mine"):
        booking = self.request(venue_id, event_id)
        return self.service.approve_booking(booking.bookingId, CALLER["userId"], "Free that day")

    def block(self, venue_id, start=at(10), end=at(12), acknowledge=False, reason="maintenance"):
        return self.service.record_unavailability(
            venue_id,
            UnavailabilityCreate(startsAt=start, endsAt=end, reason=reason, acknowledgeConflicts=acknowledge),
            CALLER,
        )

    def replace(self, booking_id, venue_id, caller=COORDINATOR, event=None, **overrides):
        return self.service.request_replacement(
            booking_id,
            ReplacementRequest(venueId=venue_id, **overrides),
            caller,
            event or self.event,
        )

    def refused(self, call, status_code):
        with self.assertRaises(HTTPException) as ctx:
            call()
        self.assertEqual(ctx.exception.status_code, status_code)
        return ctx.exception.detail


class TestRecordingABlock(ReplacementCase):
    """Recording a block leaves the approved booking and does not touch the event."""

    def test_a_block_over_an_approved_booking_needs_confirmation_and_then_leaves_it_approved(self):
        booking = self.approve(self.venue.venueId)
        before = self.event.model_dump()

        detail = self.refused(lambda: self.block(self.venue.venueId), 409)

        self.assertIn("e-mine", detail)
        self.assertFalse(self.service.get_booking(booking.bookingId).affectedByUnavailability)
        saved = self.block(self.venue.venueId, acknowledge=True)
        self.assertEqual(saved.reason, "maintenance")
        self.assertEqual(saved.createdBy, CALLER["userId"])
        kept = self.service.get_booking(booking.bookingId)
        self.assertEqual(kept.status, "approved")
        self.assertTrue(kept.affectedByUnavailability)
        self.assertEqual(self.event.model_dump(), before)

    def test_a_pending_request_does_not_need_confirmation(self):
        self.request(self.venue.venueId)

        saved = self.block(self.venue.venueId)

        self.assertEqual(saved.venueId, self.venue.venueId)
        self.assertEqual(self.service.list_bookings(status="pending")[0].status, "pending")

    def test_a_block_that_only_touches_the_occupied_window_is_saved_without_confirmation(self):
        self.approve(self.venue.venueId)

        # 10:00-12:00 with 30 minutes setup and 60 minutes turnaround occupies 09:30-13:00.
        saved = self.block(self.venue.venueId, start=at(13), end=at(15))

        self.assertEqual(saved.startsAt, at(13))
        self.assertFalse(self.service.list_bookings()[0].affectedByUnavailability)

    def test_a_block_during_setup_counts_as_overlapping(self):
        self.approve(self.venue.venueId)

        detail = self.refused(lambda: self.block(self.venue.venueId, start=at(9), end=at(9) + timedelta(minutes=31)), 409)

        self.assertIn("confirmed booking", detail)

    def test_the_end_must_be_after_the_start_and_the_reason_cannot_be_blank(self):
        self.assertIn("after the start", self.refused(lambda: self.block(self.venue.venueId, start=at(12), end=at(10)), 422))
        self.assertIn("reason", self.refused(lambda: self.block(self.venue.venueId, reason="   "), 422))

    def test_an_unknown_venue_is_not_found(self):
        self.refused(lambda: self.block("missing"), 404)


class TestReplacementRequest(ReplacementCase):
    """The assigned coordinator can search for and request another venue."""

    def test_search_drops_the_blocked_venue_and_keeps_another_that_suits(self):
        self.approve(self.venue.venueId)
        self.block(self.venue.venueId, acknowledge=True)

        found = self.service.search_venues(
            starts_at=at(10),
            ends_at=at(12),
            min_capacity=10,
            layout="Theatre",
            exclude_event_id="e-mine",
            event=self.event,
        )

        ids = [row.venueId for row in found]
        self.assertNotIn(self.venue.venueId, ids)
        self.assertIn(self.other.venueId, ids)

    def test_a_suitable_replacement_cancels_the_original_and_leaves_it_readable(self):
        original = self.approve(self.venue.venueId)
        self.block(self.venue.venueId, acknowledge=True)
        before = self.event.model_dump()

        created = self.replace(original.bookingId, self.other.venueId, coordinatorNotes="Same run of show.")

        self.assertEqual(created.status, "pending")
        self.assertEqual(created.venueId, self.other.venueId)
        self.assertEqual(created.startsAt, original.startsAt)
        self.assertEqual(created.endsAt, original.endsAt)
        self.assertEqual(created.eventSnapshot["eventName"], "AI Summit")
        self.assertEqual(created.eventSnapshot["expectedAttendance"], 10)
        self.assertEqual(created.coordinatorNotes, "Same run of show.")
        kept = self.service.get_booking(original.bookingId)
        self.assertEqual(kept.status, "cancelled")
        self.assertEqual(kept.venueId, self.venue.venueId)
        self.assertEqual(kept.startsAt, original.startsAt)
        self.assertFalse(kept.affectedByUnavailability)
        self.assertEqual(self.event.model_dump(), before)

    def test_the_events_other_approved_booking_stays(self):
        original = self.approve(self.venue.venueId)
        other = self.approve(self.other.venueId)
        third = self.venue_named("Harbour Room", "HR-C")
        self.block(self.venue.venueId, acknowledge=True)

        detail = self.refused(lambda: self.replace(original.bookingId, self.other.venueId), 409)

        self.assertIn("approved", detail)
        self.assertEqual(self.service.get_booking(original.bookingId).status, "approved")
        self.assertEqual(self.service.get_booking(other.bookingId).status, "approved")
        created = self.replace(original.bookingId, third.venueId)
        self.assertEqual(created.venueId, third.venueId)
        self.assertEqual(self.service.get_booking(other.bookingId).status, "approved")

    def test_a_pending_booking_of_the_new_venue_is_refused_and_the_original_stays(self):
        original = self.approve(self.venue.venueId)
        self.request(self.other.venueId)
        self.block(self.venue.venueId, acknowledge=True)

        detail = self.refused(lambda: self.replace(original.bookingId, self.other.venueId), 409)

        self.assertIn("pending", detail)
        self.assertEqual(self.service.get_booking(original.bookingId).status, "approved")

    def test_an_unsuitable_venue_is_refused_and_the_original_stays_approved(self):
        original = self.approve(self.venue.venueId)
        self.block(self.venue.venueId, acknowledge=True)
        boardroom = self.service.create_venue(
            venue_create(
                name="Skyline Boardroom",
                code="SB",
                layouts=[Layout(name="Boardroom", capacity=20)],
                operatingHours=[OperatingHours(day=day, opens="08:00", closes="18:00") for day in WEEKDAYS],
            ),
            CALLER,
        )

        detail = self.refused(lambda: self.replace(original.bookingId, boardroom.venueId), 409)

        self.assertIn("not suitable", detail)
        self.assertEqual(self.service.get_booking(original.bookingId).status, "approved")
        self.assertEqual(len(self.service.list_bookings()), 1)

    def test_a_warning_must_be_acknowledged_and_is_then_stored(self):
        original = self.approve(self.venue.venueId)
        self.block(self.venue.venueId, acknowledge=True)
        tight = self.event.model_copy(update={"expectedAttendance": 95})

        detail = self.refused(lambda: self.replace(original.bookingId, self.other.venueId, event=tight), 409)

        self.assertIn("warnings", detail)
        self.assertEqual(self.service.get_booking(original.bookingId).status, "approved")
        created = self.replace(original.bookingId, self.other.venueId, event=tight, acknowledgeWarnings=True)
        self.assertTrue(created.warnings)
        self.assertEqual(self.service.get_booking(original.bookingId).status, "cancelled")

    def test_only_the_assigned_coordinator_can_replace_an_affected_approved_booking(self):
        original = self.approve(self.venue.venueId)
        self.block(self.venue.venueId, acknowledge=True)

        self.assertIn("assigned", self.refused(lambda: self.replace(original.bookingId, self.other.venueId, caller=OTHER), 403))
        confirmed = self.event.model_copy(update={"status": "confirmed"})
        self.assertIn("planning", self.refused(lambda: self.replace(original.bookingId, self.other.venueId, event=confirmed), 409))
        self.refused(lambda: self.replace("missing", self.other.venueId), 404)

        pending = self.request(self.other.venueId)
        self.assertIn("approved", self.refused(lambda: self.replace(pending.bookingId, self.venue.venueId), 409))
        clear = self.venue_named("Clear Hall", "CL")
        untouched = self.approve(clear.venueId)
        self.assertIn("not affected", self.refused(lambda: self.replace(untouched.bookingId, self.other.venueId), 409))
