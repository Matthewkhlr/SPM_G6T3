from unittest.mock import MagicMock, patch

import httpx
from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, venue_create

HEADERS = {"Authorization": "Bearer token"}
NEW_VENUE = {"name": "Riverside Room", "location": "City", "layouts": [{"name": "Theatre", "capacity": 10}]}


def signed_in_as(role):
    """Stand in for user-service's /users/me, so the real resolve_caller role check still runs."""
    response = MagicMock(status_code=200)
    response.json.return_value = {"userId": f"u-{role}", "userName": role, "role": role}
    client = MagicMock()
    client.__enter__.return_value.get.return_value = response
    fake_httpx = MagicMock(Client=MagicMock(return_value=client), HTTPError=httpx.HTTPError)
    return patch("shared.auth.roles.httpx", fake_httpx)


class TestVenueRouteGuards(VenueCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.venue_id = self.service.create_venue(venue_create(), CALLER).venueId

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_venue_staff_can_add_edit_and_retire_a_venue(self):
        with signed_in_as("venue"):
            created = self.client.post("/venues", headers=HEADERS, json=NEW_VENUE)
            edited = self.client.patch(f"/venues/{self.venue_id}", headers=HEADERS, json={"description": "Edited"})
            retired = self.client.post(f"/venues/{self.venue_id}/retire", headers=HEADERS)

        self.assertEqual(created.status_code, 201)
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(retired.status_code, 200)

    def test_coordinators_and_technical_support_can_read_but_not_change_venues(self):
        for role in ("coordinator", "techsupport"):
            with self.subTest(role=role), signed_in_as(role):
                self.assertEqual(self.client.get("/venues", headers=HEADERS).status_code, 200)
                self.assertEqual(self.client.get(f"/venues/{self.venue_id}", headers=HEADERS).status_code, 200)
                self.assertEqual(
                    self.client.get(f"/venues/{self.venue_id}/activity-log", headers=HEADERS).status_code, 200
                )
                self.assertEqual(self.client.post("/venues", headers=HEADERS, json=NEW_VENUE).status_code, 403)
                self.assertEqual(
                    self.client.patch(
                        f"/venues/{self.venue_id}", headers=HEADERS, json={"description": "Nope"}
                    ).status_code,
                    403,
                )
                self.assertEqual(self.client.post(f"/venues/{self.venue_id}/retire", headers=HEADERS).status_code, 403)

        venue = self.service.get_venue(self.venue_id)
        self.assertTrue(venue.isActive)
        self.assertEqual(venue.description, "Main hall")

    def test_organisers_and_attendees_cannot_see_the_catalogue(self):
        for role in ("organiser", "attendee"):
            with self.subTest(role=role), signed_in_as(role):
                self.assertEqual(self.client.get("/venues", headers=HEADERS).status_code, 403)
                self.assertEqual(self.client.get(f"/venues/{self.venue_id}", headers=HEADERS).status_code, 403)

    def test_a_zero_layout_capacity_sent_to_the_api_is_refused(self):
        with signed_in_as("venue"):
            response = self.client.patch(
                f"/venues/{self.venue_id}",
                headers=HEADERS,
                json={"layouts": [{"name": "Theatre", "capacity": 0}]},
            )

        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.get_venue(self.venue_id).capacity, 100)
