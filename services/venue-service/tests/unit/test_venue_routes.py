from datetime import timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.venue import EventFacts
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import CALLER, COORDINATOR, END, START


class TestVenueRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.venue.resolve_caller", return_value=CALLER)
        self.caller.start()
        # Booking requests read the event and notify Venue Staff over HTTP;
        # stand in for those so this test stays about the routes themselves.
        event = EventFacts(coordinatorId=COORDINATOR["userId"], status="approved", expectedAttendance=10)
        self.others = [
            patch("app.routers.venue.fetch_event_facts", return_value=event),
            patch("app.routers.venue.notify_venue_staff", return_value=1),
        ]
        for other in self.others:
            other.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        for other in self.others:
            other.stop()
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_catalogue_and_booking_routes(self):
        created = self.client.post(
            "/venues",
            headers=self.headers,
            json={
                "name": "Marina Hall A",
                "location": "HarbourFront",
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [
                    {"day": day, "opens": "00:00", "closes": "24:00"}
                    for day in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
                ],
                "facilities": ["PA"],
                "accessibility": ["Ramp"],
            },
        )
        self.assertEqual(created.status_code, 201)
        venue_id = created.json()["venueId"]

        self.assertEqual(self.client.get("/venues", headers=self.headers).status_code, 200)
        self.assertEqual(self.client.get(f"/venues/{venue_id}", headers=self.headers).status_code, 200)
        self.assertEqual(
            self.client.patch(f"/venues/{venue_id}", headers=self.headers, json={"name": "Marina Hall B"}).status_code,
            200,
        )
        self.assertEqual(self.client.get(f"/venues/{venue_id}/activity-log", headers=self.headers).status_code, 200)

        self.caller.stop()
        self.caller = patch("app.routers.venue.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        booking = self.client.post(
            "/venues/bookings",
            headers=self.headers,
            json={
                "venueId": venue_id,
                "eventId": "e1",
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
                "setupStartsAt": (START - timedelta(hours=1)).isoformat(),
                "teardownEndsAt": (END + timedelta(hours=1)).isoformat(),
            },
        )
        self.assertEqual(booking.status_code, 201)
        second = self.client.post(
            "/venues/bookings",
            headers=self.headers,
            json={
                "venueId": venue_id,
                "eventId": "e2",
                "startsAt": (START + timedelta(days=1)).isoformat(),
                "endsAt": (END + timedelta(days=1)).isoformat(),
                "setupStartsAt": (START + timedelta(days=1, hours=-1)).isoformat(),
                "teardownEndsAt": (END + timedelta(days=1, hours=1)).isoformat(),
            },
        )
        self.assertEqual(second.status_code, 201)

        self.caller.stop()
        self.caller = patch("app.routers.venue.resolve_caller", return_value=CALLER)
        self.caller.start()
        approved = self.client.post(
            f"/venues/bookings/{booking.json()['bookingId']}/approve",
            headers=self.headers,
            json={"reason": "Free"},
        )
        self.assertEqual(approved.status_code, 200)
        rejected = self.client.post(
            f"/venues/bookings/{second.json()['bookingId']}/reject",
            headers=self.headers,
            json={"reason": "Closed"},
        )
        self.assertEqual(rejected.status_code, 200)
        retired = self.client.post(f"/venues/{venue_id}/retire", headers=self.headers, params={"confirm": True})
        self.assertEqual(retired.status_code, 200)
        self.assertFalse(retired.json()["isActive"])
