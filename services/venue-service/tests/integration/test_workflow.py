"""Venue catalogue and the attendee-safe booking summary over HTTP and SQL."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

VENUE = {"userId": "u-venue", "userName": "Carol", "role": "venue"}


class TestVenueWorkflow(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.venue.resolve_caller", return_value=VENUE)
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_catalogue_and_public_summary(self):
        gate = app.dependency_overrides.pop(require_authenticated_user)
        self.assertEqual(self.client.get("/venues").status_code, 401)
        app.dependency_overrides[require_authenticated_user] = gate
        created = self.client.post(
            "/venues",
            headers=self.headers,
            json={
                "code": "MH-A",
                "name": "Marina Hall A",
                "location": "HarbourFront Centre",
                "address": "1 HarbourFront Walk",
                "floor": "2",
                "description": "Main hall",
                "facilities": ["Projector"],
                "accessibility": ["Wheelchair accessible"],
                "layouts": [{"name": "Theatre", "capacity": 100}],
                "operatingHours": [{"day": "Mon", "opens": "08:00", "closes": "18:00"}],
                "setupMinutes": 30,
                "turnaroundMinutes": 60,
            },
        )
        self.assertEqual(created.status_code, 201)
        summary = self.client.get(
            "/venues/bookings/public-summary", headers=self.headers, params={"eventId": "e1"}
        )
        self.assertEqual(summary.status_code, 200)
        self.assertEqual(summary.json()["venueName"], "")
        listed = self.client.get("/venues", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["name"], "Marina Hall A")
