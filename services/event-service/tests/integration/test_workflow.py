"""Event intake, requirements, readiness, and public browse over HTTP and SQL."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

ORGANISER = {"userId": "org-1", "organisationId": "o1", "role": "organiser", "userName": "Amy"}
COORDINATOR = {"userId": "coord-1", "role": "coordinator", "userName": "Ben"}


class TestEventWorkflow(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.organiser = patch("app.routers.event.current_organiser", return_value=ORGANISER)
        def as_role(_authorization, _url, allowed_roles=None):
            if allowed_roles == {"coordinator"}:
                return COORDINATOR
            return ORGANISER

        self.caller = patch("app.routers.event.resolve_caller", side_effect=as_role)
        self.counts = patch("app.services.event_service.registration_count", return_value=0)
        self.open_counts = patch("app.services.event_followup.registration_count", return_value=0)
        self.organiser.start()
        self.caller.start()
        self.counts.start()
        self.open_counts.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.open_counts.stop()
        self.counts.stop()
        self.caller.stop()
        self.organiser.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_draft_requirements_submit_readiness_and_browse(self):
        gate = app.dependency_overrides.pop(require_authenticated_user)
        self.assertEqual(self.client.get("/events").status_code, 401)
        app.dependency_overrides[require_authenticated_user] = gate
        draft = self.client.post("/events", headers=self.headers, json={"eventName": "Summit"})
        self.assertEqual(draft.status_code, 201)
        self.assertEqual(draft.json()["status"], "draft")
        event_id = draft.json()["eventId"]

        options = self.client.get("/events/requirement-options")
        self.assertEqual(options.status_code, 200)
        self.assertIn("Theatre", options.json()["layouts"])

        saved = self.client.patch(
            f"/events/{event_id}",
            headers=self.headers,
            json={
                "layoutPreference": "Theatre",
                "preferredLocation": "HarbourFront",
                "requiredFacilities": ["Projector"],
                "accessibilityNeeds": ["Wheelchair accessible"],
                "equipmentLines": [{"equipmentId": "eq1", "quantity": 2, "technicalNotes": "HDMI"}],
            },
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["equipmentLines"][0]["quantity"], 2)

        submitted = self.client.post(
            "/events",
            headers=self.headers,
            json={
                "eventName": "Open summit",
                "purpose": "Share",
                "description": "A public day",
                "category": "conference",
                "proposedStartAt": "2026-12-01T09:00:00",
                "proposedEndAt": "2026-12-01T17:00:00",
                "expectedAttendance": 20,
                "registrationEnabled": True,
                "registrationOpensAt": "2026-09-01T00:00:00",
                "registrationClosesAt": "2026-11-30T00:00:00",
                "capacity": 20,
            },
        )
        self.assertEqual(submitted.status_code, 201)
        open_id = submitted.json()["eventId"]

        line = self.client.post(
            f"/events/{open_id}/readiness-items",
            headers=self.headers,
            json={"category": "venue", "handlerId": "u3", "status": "outstanding"},
        )
        self.assertEqual(line.status_code, 201)
        listed = self.client.get(f"/events/{open_id}/readiness", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertTrue(any(row["category"] == "equipment" for row in listed.json()))

        # The new event is submitted, so it is not on the attendee browse list.
        browse = self.client.get("/events/open-for-registration", headers=self.headers)
        self.assertEqual(browse.status_code, 200)
        self.assertNotIn(open_id, [row["eventId"] for row in browse.json()])
