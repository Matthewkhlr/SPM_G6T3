from datetime import timedelta

from fastapi import HTTPException

from app.schemas.venue import Layout, VenueBookingCreate, VenueCreate
from tests.unit.support import CALLER, END, START, VenueCase


class TestVenueConflicts(VenueCase):
    def setUp(self):
        super().setUp()
        self.venue = self.service.create_venue(
            VenueCreate(
                name="Marina Hall A",
                location="HarbourFront",
                facilities=["PA", "Stage"],
                layouts=[Layout(name="Theatre", capacity=100), Layout(name="Classroom", capacity=40)],
            ),
            CALLER,
        )

    def _booking(self, event_id, starts, ends):
        return self.service.create_booking(
            VenueBookingCreate(
                venueId=self.venue.venueId,
                eventId=event_id,
                startsAt=starts,
                endsAt=ends,
                setupStartsAt=starts - timedelta(hours=1),
                teardownEndsAt=ends + timedelta(hours=1),
            ),
            "u-coord",
        )

    def test_a_second_overlapping_approval_is_refused(self):
        first = self._booking("e1", START, END)
        second = self._booking("e2", START + timedelta(hours=2), END + timedelta(hours=2))
        self.service.approve_booking(first.bookingId, "u-venue", "First claim")

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_booking(second.bookingId, "u-venue", "Clash")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service._require_booking(second.bookingId).status, "pending")

    def test_unavailability_blocks_a_booking_in_that_period(self):
        self.assertTrue(
            hasattr(self.service, "record_unavailability"),
            "record_unavailability is not implemented",
        )

        self.service.record_unavailability(self.venue.venueId, START, END, "Maintenance", CALLER)
        booking = self._booking("e1", START, END)

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_booking(booking.bookingId, "u-venue", "During maintenance")

        self.assertEqual(ctx.exception.status_code, 409)

    def test_search_filters_by_capacity_and_facility(self):
        self.assertTrue(hasattr(self.service, "search_venues"), "search_venues is not implemented")
        self.service.create_venue(
            VenueCreate(
                name="Boardroom",
                location="City",
                facilities=["Whiteboard"],
                layouts=[Layout(name="Boardroom", capacity=12)],
            ),
            CALLER,
        )

        matches = self.service.search_venues(min_capacity=80, facility="PA")

        self.assertEqual([row.name for row in matches], ["Marina Hall A"])

    def test_suitability_fails_when_attendance_exceeds_the_layout(self):
        self.assertTrue(hasattr(self.service, "check_suitability"), "check_suitability is not implemented")

        too_big = self.service.check_suitability(self.venue.venueId, expected_attendance=150, layout="Theatre")
        fits = self.service.check_suitability(
            self.venue.venueId, expected_attendance=80, layout="Theatre", facilities=["PA"]
        )

        self.assertFalse(too_big["suitable"])
        self.assertIn("150", too_big["reason"])
        self.assertTrue(fits["suitable"])
