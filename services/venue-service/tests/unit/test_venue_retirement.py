from fastapi import HTTPException

from tests.unit.support import CALLER, VenueCase, booking_create, venue_create


class TestVenueRetirement(VenueCase):
    def test_retire_blocks_one_confirmed_upcoming_booking_until_confirmed(self):
        created = self.service.create_venue(venue_create(), CALLER)
        booking = self.service.create_booking(booking_create(created.venueId), "u-coord")
        self.service.approve_booking(booking.bookingId, "u-venue", "Free that day")

        with self.assertRaises(HTTPException) as ctx:
            self.service.retire_venue(created.venueId, CALLER)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("1 confirmed upcoming booking ", ctx.exception.detail)

        retired = self.service.retire_venue(created.venueId, CALLER, confirm=True)
        self.assertFalse(retired.isActive)

    def test_retire_names_every_confirmed_upcoming_booking(self):
        created = self.service.create_venue(venue_create(), CALLER)
        first = self.service.create_booking(booking_create(created.venueId, eventId="e1"), "u-coord")
        second = self.service.create_booking(booking_create(created.venueId, eventId="e2"), "u-coord")
        self.service.approve_booking(first.bookingId, "u-venue", None)
        self.service.approve_booking(second.bookingId, "u-venue", "Overlap")

        with self.assertRaises(HTTPException) as ctx:
            self.service.retire_venue(created.venueId, CALLER, confirm=False)

        self.assertIn("2 confirmed upcoming bookings", ctx.exception.detail)
