import unittest
from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.venue import EventFacts, OperatingHours
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
EVENT = EventFacts(
    eventName="AI Summit",
    status="planning",
    coordinatorId="u-coordinator",
    organisationId="org-1",
    organisationName="Apex Partners",
    expectedAttendance=10,
    layoutPreference="Theatre",
    proposedStartAt=datetime(2030, 1, 7, 10),
    proposedEndAt=datetime(2030, 1, 7, 12),
)


class TestReplacementRoutes(VenueCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        hours = [OperatingHours(day=d, opens="08:00", closes="18:00") for d in ALL_DAYS]
        self.venue_id = self.service.create_venue(venue_create(operatingHours=hours), CALLER).venueId
        self.other_id = self.service.create_venue(
            venue_create(name="Exhibition Hall B", code="EH-B", operatingHours=hours), CALLER
        ).venueId
        self.patches = {
            "event": patch("app.routers.venue.fetch_event_facts", return_value=EVENT),
            "notify": patch("app.routers.venue.notify_venue_staff", return_value=2),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def call(self, role, method, path, body=None):
        with signed_in_as(role):
            return self.client.request(method, path, headers=HEADERS, json=body)

    def affected_booking(self):
        with signed_in_as("coordinator"):
            created = self.client.post(
                "/venues/bookings",
                headers=HEADERS,
                json={
                    "venueId": self.venue_id,
                    "eventId": "e1",
                    "startsAt": "2030-01-07T10:00:00Z",
                    "endsAt": "2030-01-07T12:00:00Z",
                },
            )
        self.assertEqual(created.status_code, 201, created.text)
        booking_id = created.json()["bookingId"]
        approved = self.service.approve_booking(booking_id, CALLER["userId"], None)
        blocked = self.call(
            "venue",
            "POST",
            f"/venues/{self.venue_id}/unavailability",
            {
                "startsAt": "2030-01-07T10:00:00Z",
                "endsAt": "2030-01-07T12:00:00Z",
                "reason": "maintenance",
                "acknowledgeConflicts": True,
            },
        )
        self.assertEqual(blocked.status_code, 201, blocked.text)
        return approved.bookingId

    def test_recording_a_block_does_not_read_the_event_and_a_coordinator_cannot_record_one(self):
        self.mocks["event"].reset_mock()
        saved = self.call(
            "venue",
            "POST",
            f"/venues/{self.venue_id}/unavailability",
            {"startsAt": "2030-01-07T10:00:00Z", "endsAt": "2030-01-07T12:00:00Z", "reason": "maintenance"},
        )

        self.assertEqual(saved.status_code, 201, saved.text)
        self.mocks["event"].assert_not_called()
        refused = self.call(
            "coordinator",
            "POST",
            f"/venues/{self.venue_id}/unavailability",
            {"startsAt": "2030-01-07T10:00:00Z", "endsAt": "2030-01-07T12:00:00Z", "reason": "maintenance"},
        )
        self.assertEqual(refused.status_code, 403)

    def test_the_assigned_coordinator_can_request_a_replacement_and_staff_are_told(self):
        booking_id = self.affected_booking()
        self.mocks["notify"].reset_mock()
        self.mocks["event"].reset_mock()

        created = self.call(
            "coordinator",
            "POST",
            f"/venues/bookings/{booking_id}/replacement",
            {"venueId": self.other_id},
        )

        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["status"], "pending")
        self.assertEqual(created.json()["venueId"], self.other_id)
        self.mocks["event"].assert_called_once()
        self.assertEqual(self.mocks["notify"].call_count, 2)
        original = self.call("coordinator", "GET", f"/venues/bookings/{booking_id}")
        self.assertEqual(original.status_code, 200)
        self.assertEqual(original.json()["status"], "cancelled")
        refused = self.call("venue", "POST", f"/venues/bookings/{booking_id}/replacement", {"venueId": self.other_id})
        self.assertEqual(refused.status_code, 403)


if __name__ == "__main__":
    unittest.main()
