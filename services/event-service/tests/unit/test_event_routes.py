from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import COORDINATOR, ORGANISER, TECH


class TestEventRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1", "email": "amy@connectsphere.com"}
        self.counts = patch("app.services.event_service.registration_count", return_value=0)
        self.organiser = patch("app.routers.event.current_organiser", return_value=ORGANISER)
        self.tech = patch("app.routers.event.current_technical_support", return_value=TECH)
        self.caller = patch("app.routers.event.resolve_caller", return_value=COORDINATOR)
        self.counts.start()
        self.organiser.start()
        self.tech.start()
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        self.tech.stop()
        self.organiser.stop()
        self.counts.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_http_create_list_get_decide_and_assign(self):
        headers = {"Authorization": "Bearer token"}
        body = {
            "eventName": "Summit",
            "proposedStartAt": "2026-10-06T09:00:00",
            "proposedEndAt": "2026-10-06T17:00:00",
            "expectedAttendance": 10,
        }
        created = self.client.post("/events", headers=headers, json=body)
        self.assertEqual(created.status_code, 201)
        event_id = created.json()["eventId"]

        self.assertEqual(self.client.get("/events", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/events/all", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/events/confirmed", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/events/queue", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/events/mine", headers=headers).status_code, 200)
        self.assertEqual(self.client.get("/events/upcoming/technical", headers=headers).status_code, 200)
        self.assertEqual(self.client.get(f"/events/{event_id}", headers=headers).status_code, 200)
        self.assertEqual(self.client.get(f"/events/{event_id}/activity-log", headers=headers).status_code, 200)

        approved = self.client.post(f"/events/{event_id}/approve", headers=headers, json={})
        self.assertEqual(approved.status_code, 200)

        rejected_source = self.client.post("/events", headers=headers, json=body)
        rejected = self.client.post(
            f"/events/{rejected_source.json()['eventId']}/reject",
            headers=headers,
            json={"reason": "Dates clash"},
        )
        self.assertEqual(rejected.status_code, 200)

        assigned = self.client.post(
            f"/events/{event_id}/assign-coordinator",
            headers=headers,
            json={"coordinatorId": "coord-1"},
        )
        self.assertEqual(assigned.status_code, 201)

    def test_registration_access_route_returns_capacity_for_the_organiser(self):
        self.caller.stop()
        self.caller = patch("app.routers.event.resolve_caller", return_value=ORGANISER)
        self.caller.start()
        headers = {"Authorization": "Bearer token"}
        created = self.client.post(
            "/events",
            headers=headers,
            json={
                "eventName": "Summit",
                "proposedStartAt": "2026-10-06T09:00:00",
                "proposedEndAt": "2026-10-06T17:00:00",
                "expectedAttendance": 10,
                "registrationEnabled": True,
                "registrationOpensAt": "2026-09-01T00:00:00",
                "registrationClosesAt": "2026-10-01T00:00:00",
                "capacity": 50,
            },
        )
        access = self.client.get(
            f"/events/{created.json()['eventId']}/registration-access",
            headers=headers,
        )

        self.assertEqual(created.status_code, 201)
        self.assertEqual(access.status_code, 200)
        self.assertEqual(access.json()["capacity"], 50)
        self.assertEqual(access.json()["registrationOpensAt"], "2026-09-01T00:00:00")
        self.assertNotIn("organiserId", access.json())

    def test_http_draft_update_submit_and_discard(self):
        headers = {"Authorization": "Bearer token"}
        created = self.client.post("/events/drafts", headers=headers, json={"eventName": "Draft summit"})
        self.assertEqual(created.status_code, 201)
        event_id = created.json()["eventId"]

        renamed = self.client.put(f"/events/{event_id}/draft", headers=headers, json={"eventName": "Renamed draft"})
        self.assertEqual(renamed.status_code, 200)
        self.assertEqual(self.client.get("/events/drafts/mine", headers=headers).status_code, 200)

        submitted = self.client.post(
            f"/events/{event_id}/submit",
            headers=headers,
            json={
                "eventName": "Renamed draft",
                "proposedStartAt": "2026-10-06T09:00:00",
                "proposedEndAt": "2026-10-06T17:00:00",
                "expectedAttendance": 4,
            },
        )
        self.assertEqual(submitted.status_code, 200)

        another = self.client.post("/events/drafts", headers=headers, json={"eventName": "Throwaway"})
        discarded = self.client.delete(f"/events/{another.json()['eventId']}", headers=headers)
        self.assertEqual(discarded.status_code, 200)
        self.assertEqual(discarded.json()["status"], "discarded")
