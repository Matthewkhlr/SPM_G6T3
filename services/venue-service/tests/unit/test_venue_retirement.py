from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException

from tests.unit.support import CALLER, END, START, VenueCase, booking_create, venue_create

NOW = datetime(2030, 1, 1, 9, 0, 0)


class _FrozenDatetime(datetime):
    @classmethod
    def utcnow(cls):
        return NOW


def frozen_now():
    return patch("app.services.venue_service.datetime", _FrozenDatetime)


class TestVenueRetirement(VenueCase):
    def _approved_booking(self, venue_id, starts_at, **overrides):
        booking = self.service.create_booking(
            booking_create(
                venue_id,
                startsAt=starts_at,
                endsAt=starts_at + timedelta(hours=8),
                setupStartsAt=starts_at - timedelta(hours=1),
                teardownEndsAt=starts_at + timedelta(hours=9),
                **overrides,
            ),
            "u-coord",
        )
        self.service.approve_booking(booking.bookingId, "u-venue", None)
        return booking

    def test_retire_blocks_one_confirmed_upcoming_booking_until_confirmed(self):
        created = self.service.create_venue(venue_create(), CALLER)
        booking = self.service.create_booking(booking_create(created.venueId), "u-coord")
        self.service.approve_booking(booking.bookingId, "u-venue", "Free that day")

        with self.assertRaises(HTTPException) as ctx:
            self.service.retire_venue(created.venueId, CALLER)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("1 confirmed upcoming booking ", ctx.exception.detail)
        self.assertTrue(self.service.get_venue(created.venueId).isActive)

        retired = self.service.retire_venue(created.venueId, CALLER, confirm=True)
        self.assertFalse(retired.isActive)

    def test_retire_names_every_confirmed_upcoming_booking(self):
        created = self.service.create_venue(venue_create(), CALLER)
        first = self.service.create_booking(booking_create(created.venueId, eventId="e1"), "u-coord")
        # A day apart: two overlapping confirmed bookings can no longer exist (SPM-64).
        second = self.service.create_booking(
            booking_create(
                created.venueId, eventId="e2", startsAt=START + timedelta(days=1), endsAt=END + timedelta(days=1)
            ),
            "u-coord",
        )
        self.service.approve_booking(first.bookingId, "u-venue", None)
        self.service.approve_booking(second.bookingId, "u-venue", "Next day")

        with self.assertRaises(HTTPException) as ctx:
            self.service.retire_venue(created.venueId, CALLER, confirm=False)

        self.assertIn("2 confirmed upcoming bookings", ctx.exception.detail)
        self.assertIn("event e1", ctx.exception.detail)
        self.assertIn("event e2", ctx.exception.detail)

    def test_a_pending_upcoming_booking_does_not_block_retire(self):
        created = self.service.create_venue(venue_create(), CALLER)
        self.service.create_booking(booking_create(created.venueId), "u-coord")

        retired = self.service.retire_venue(created.venueId, CALLER)

        self.assertFalse(retired.isActive)

    def test_a_rejected_upcoming_booking_does_not_block_retire(self):
        created = self.service.create_venue(venue_create(), CALLER)
        booking = self.service.create_booking(booking_create(created.venueId), "u-coord")
        self.service.reject_booking(booking.bookingId, "u-venue", "Closed")

        retired = self.service.retire_venue(created.venueId, CALLER)

        self.assertFalse(retired.isActive)

    def test_a_confirmed_booking_starting_exactly_now_no_longer_blocks_retire(self):
        created = self.service.create_venue(venue_create(), CALLER)
        self._approved_booking(created.venueId, NOW)

        with frozen_now():
            retired = self.service.retire_venue(created.venueId, CALLER)

        self.assertFalse(retired.isActive)

    def test_a_confirmed_booking_starting_one_second_from_now_still_blocks_retire(self):
        created = self.service.create_venue(venue_create(), CALLER)
        self._approved_booking(created.venueId, NOW + timedelta(seconds=1))

        with frozen_now(), self.assertRaises(HTTPException) as ctx:
            self.service.retire_venue(created.venueId, CALLER)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("starting 01 Jan 2030, 09:00 AM UTC", ctx.exception.detail)

    def test_retire_writes_a_retired_entry_to_the_activity_log(self):
        created = self.service.create_venue(venue_create(), CALLER)

        self.service.retire_venue(created.venueId, CALLER)

        entry = next(row for row in self.service.get_activity_log(created.venueId) if row.action == "retired")
        self.assertEqual(entry.changes, {"isActive": {"old": True, "new": False}})
        self.assertEqual(entry.changedBy, "u-venue")
