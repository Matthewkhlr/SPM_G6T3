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
                setupMinutes=30,
                turnaroundMinutes=60,
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
