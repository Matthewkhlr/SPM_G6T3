"""SPM-112: availability and conflict checks include each venue's setup and turnaround time."""

from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException

from app.models.venue_booking import VenueBooking
from app.models.venue_info import VenueInfo
from app.models.venue_unavailability import VenueUnavailability
from app.schemas.venue import EventFacts, OperatingHours, SuitabilityRequest, VenueUpdate
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create

MONDAY = datetime(2030, 1, 7)
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def at(hour, minute=0):
    return MONDAY + timedelta(hours=hour, minutes=minute)


class OccupiedWindowCase(VenueCase):
    """The customer's example: a venue with 30 minutes setup and 45 minutes
    turnaround, open all day, so a 10:00 to 12:00 event occupies 09:30 to 12:45."""

    def setUp(self):
        super().setUp()
        self.hall = self.service.create_venue(
            venue_create(
                setupMinutes=30,
                turnaroundMinutes=45,
                operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS],
            ),
            CALLER,
        )

    def request(self, starts_at, ends_at, event_id=None):
        return self.service.create_booking(
            booking_create(
                self.hall.venueId, eventId=event_id or f"e-{uuid4().hex[:6]}", startsAt=starts_at, endsAt=ends_at
            ),
            "u-coord",
        )


class TestTheWindowOfABooking(OccupiedWindowCase):
    """AC1: start minus the venue's setup time through end plus its turnaround time."""

    def test_the_customers_example_occupies_0930_to_1245(self):
        booking = self.service.get_booking(self.request(at(10), at(12)).bookingId)

        self.assertEqual((booking.setupStartsAt, booking.teardownEndsAt), (at(9, 30), at(12, 45)))

    def test_a_booking_follows_its_venues_current_setup_and_turnaround(self):
        booking = self.request(at(10), at(12))

        self.service.update_venue(self.hall.venueId, VenueUpdate(setupMinutes=15, turnaroundMinutes=60), CALLER)
        shown = self.service.get_booking(booking.bookingId)
        listed = self.service.list_bookings(event_id=booking.eventId)[0]

        self.assertEqual((shown.setupStartsAt, shown.teardownEndsAt), (at(9, 45), at(13)))
        self.assertEqual((listed.setupStartsAt, listed.teardownEndsAt), (at(9, 45), at(13)))

    def test_an_older_booking_with_a_different_stored_window_reports_the_venues_window(self):
        legacy = VenueBooking(
            bookingId="vb-legacy",
            venueId=self.hall.venueId,
            eventId="e-legacy",
            requestedBy="u-coord",
            status="approved",
            startsAt=at(10),
            endsAt=at(12),
            setupStartsAt=at(9),
            teardownEndsAt=at(13),
            createdAt=at(0),
        )
        self.db.add(legacy)
        self.db.commit()

        shown = self.service.get_booking("vb-legacy")

        self.assertEqual((shown.setupStartsAt, shown.teardownEndsAt), (at(9, 30), at(12, 45)))

    def test_approval_brings_the_stored_window_up_to_date(self):
        booking = self.request(at(10), at(12))
        self.service.update_venue(self.hall.venueId, VenueUpdate(setupMinutes=60, turnaroundMinutes=15), CALLER)

        self.service.approve_booking(booking.bookingId, "u-venue", None)
        stored = self.db.get(VenueBooking, booking.bookingId)

        self.assertEqual((stored.setupStartsAt, stored.teardownEndsAt), (at(9), at(12, 15)))

    def test_without_its_venue_record_a_booking_falls_back_to_the_stored_window(self):
        booking = self.request(at(10), at(12))
        self.db.query(VenueInfo).filter(VenueInfo.venueId == self.hall.venueId).delete()
        self.db.commit()
        self.db.expire_all()

        shown = self.service.get_booking(booking.bookingId)

        self.assertEqual((shown.setupStartsAt, shown.teardownEndsAt), (at(9, 30), at(12, 45)))
        self.assertIsNone(shown.venueName)


class TestEveryCheckUsesTheSameWindow(OccupiedWindowCase):
    """AC2 to AC4: search, suitability and approval agree, case by case. A confirmed
    10:00 to 12:00 booking holds the hall from 09:30 to 12:45."""

    CASES = {
        # name: (start, end, clashes)
        "window touches the turnaround's end": (at(13, 15), at(14), False),  # set up from 12:45
        "window touches the setup's start": (at(7), at(8, 45), False),  # turned around by 09:30
        "event starts as the other ends": (at(12), at(13), True),  # set up from 11:30
        "event ends as the other starts": (at(8), at(10), True),  # turned around until 10:45
        "inside the turnaround only": (at(13), at(14), True),  # set up from 12:30
        "inside the setup only": (at(7), at(9), True),  # turned around until 09:45
    }

    def setUp(self):
        super().setUp()
        self.service.approve_booking(self.request(at(10), at(12), "e-held").bookingId, "u-venue", None)

    def answers(self, starts_at, ends_at):
        """(search excludes the hall, suitability fails it, approval refuses it)."""
        excluded = self.service.search_venues(starts_at=starts_at, ends_at=ends_at) == []
        event = EventFacts(expectedAttendance=10, proposedStartAt=starts_at, proposedEndAt=ends_at)
        verdict = self.service.check_suitability(
            SuitabilityRequest(eventId="e-new", venueId=self.hall.venueId), event
        ).verdict
        candidate = self.request(starts_at, ends_at, "e-new")
        try:
            self.service.approve_booking(candidate.bookingId, "u-venue", None)
            refused = False
            self.service.cancel_booking(candidate.bookingId, {"userId": "u-venue", "role": "venue"}, None)
        except HTTPException as exc:
            self.assertEqual(exc.status_code, 409)
            refused = True
            self.service.withdraw_booking(candidate.bookingId, {"userId": "u-coord"}, "u-coord")
        return excluded, verdict == "not suitable", refused

    def test_search_suitability_and_approval_give_the_same_answer_at_every_boundary(self):
        for name, (starts_at, ends_at, clashes) in self.CASES.items():
            with self.subTest(name):
                self.assertEqual(self.answers(starts_at, ends_at), (clashes, clashes, clashes))

    def test_unavailability_is_judged_on_the_same_window(self):
        self.db.add_all(
            [
                VenueUnavailability(
                    unavailabilityId="u-touch",
                    venueId=self.hall.venueId,
                    startsAt=at(16),
                    endsAt=at(17, 30),
                    reason="Cleaning",
                    createdBy="u-venue",
                ),
                VenueUnavailability(
                    unavailabilityId="u-after",
                    venueId=self.hall.venueId,
                    startsAt=at(19, 45),
                    endsAt=at(19, 50),
                    reason="Delivery",
                    createdBy="u-venue",
                ),
                VenueUnavailability(
                    unavailabilityId="u-overlap",
                    venueId=self.hall.venueId,
                    startsAt=at(20),
                    endsAt=at(20, 15),
                    reason="Inspection",
                    createdBy="u-venue",
                ),
            ]
        )
        self.db.commit()

        # 18:00 to 19:00 is set up from 17:30, just as the cleaning ends, and
        # turned around by 19:45, just as the delivery starts.
        self.assertEqual(self.answers(at(18), at(19)), (False, False, False))
        # 18:00 to 19:30 is turned around until 20:15, through the inspection.
        self.assertEqual(self.answers(at(18), at(19, 30)), (True, True, True))
