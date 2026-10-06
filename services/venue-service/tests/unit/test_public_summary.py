from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_booking import VenueBooking
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import CALLER, START, VenueCase, venue_create


class TestPublicSummary(VenueCase):
    def test_an_approved_booking_exposes_only_the_venue_name_and_location(self):
        venue = self.service.create_venue(venue_create(), CALLER)
        self.assertEqual(self.service.public_summary("e-none"), {"eventId": "e-none", "venueName": "", "location": ""})
        self.db.add(
            VenueBooking(
                bookingId="b1",
                venueId=venue.venueId,
                eventId="e1",
                requestedBy="u-coord",
                status="approved",
                startsAt=START,
                endsAt=START + timedelta(hours=2),
                setupStartsAt=START,
                teardownEndsAt=START + timedelta(hours=3),
                createdAt=datetime.utcnow(),
            )
        )
        self.db.commit()
        summary = self.service.public_summary("e1")
        self.assertEqual(summary["venueName"], "Marina Hall A")
        self.assertEqual(summary["location"], "HarbourFront")
        booking = self.db.query(VenueBooking).filter(VenueBooking.bookingId == "b1").one()
        booking.venueId = "missing"
        self.db.commit()
        blank = self.service.public_summary("e1")
        self.assertEqual(blank["venueName"], "")


class TestPublicSummaryRoute(ServiceTestCase):
    def test_any_signed_in_user_can_read_the_summary(self):
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        caller = patch("app.routers.venue.resolve_caller", return_value={"userId": "u5", "role": "attendee"})
        caller.start()
        client = TestClient(app)
        client.__enter__()
        try:
            response = client.get("/venues/bookings/public-summary", headers={"Authorization": "Bearer token"}, params={"eventId": "e1"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["venueName"], "")
        finally:
            client.__exit__(None, None, None)
            caller.stop()
            app.dependency_overrides.clear()
