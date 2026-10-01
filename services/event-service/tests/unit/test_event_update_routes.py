from datetime import datetime
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden
from shared.testing.cases import ServiceTestCase
from tests.unit.support import COORDINATOR, insert_event

HEADERS = {"Authorization": "Bearer token"}
VENUE = {"kind": "venue", "id": "vb-1", "summary": "Venue booking at Marina Hall A"}


class TestEventUpdateRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.affected_arrangements", return_value=[VENUE]),
            patch("app.services.event_service.flag_arrangements", return_value=[VENUE]),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", return_value=COORDINATOR)
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        insert_event(
            self.db,
            eventId="e1",
            coordinatorId=COORDINATOR["userId"],
            status="confirmed",
            proposedStartAt=datetime(2026, 12, 1, 9),
            proposedEndAt=datetime(2026, 12, 1, 17),
            expectedAttendance=120,
            internalNotes="Staff only",
        )

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_significant_fields_are_published(self):
        response = self.client.get("/events/significant-fields", headers=HEADERS)

        self.assertEqual(response.status_code, 200)
        self.assertIn("expectedAttendance", response.json()["fields"])
        self.assertIn("internalNotes", response.json()["quietFields"])

    def test_a_quiet_patch_saves_without_a_warning(self):
        response = self.client.patch("/events/e1", headers=HEADERS, json={"description": "AUTO-SPM71 quiet edit"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["description"], "AUTO-SPM71 quiet edit")
        self.assertNotIn("requiresConfirmation", response.json())
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})

    def test_a_significant_patch_is_a_409_naming_arrangements_until_confirmed(self):
        blocked = self.client.patch("/events/e1", headers=HEADERS, json={"expectedAttendance": 200})

        self.assertEqual(blocked.status_code, 409)
        self.assertTrue(blocked.json()["detail"]["requiresConfirmation"])
        self.assertEqual(blocked.json()["detail"]["arrangements"], [VENUE])

        saved = self.client.patch(
            "/events/e1", headers=HEADERS, json={"expectedAttendance": 200, "confirmSignificantChange": True}
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.json()["status"], "reconsidering")
        self.assertEqual(saved.json()["flaggedArrangements"], [VENUE])

        log = self.client.get("/events/e1/activity-log", headers=HEADERS).json()
        self.assertEqual(
            [(entry["kind"], entry["field"], entry["oldValue"], entry["newValue"]) for entry in log],
            [("edit", "expectedAttendance", "120", "200"), ("status", None, None, None)],
        )

    def test_an_invalid_patch_is_a_422(self):
        response = self.client.patch("/events/e1", headers=HEADERS, json={"eventName": ""})

        self.assertEqual(response.status_code, 422)

    def test_other_roles_cannot_patch_or_read_internal_notes(self):
        self.caller_mock.side_effect = forbidden()

        self.assertEqual(self.client.patch("/events/e1", headers=HEADERS, json={"description": "x"}).status_code, 403)
        self.assertEqual(self.client.get("/events/e1/internal-notes", headers=HEADERS).status_code, 403)

    def test_internal_notes_are_only_on_the_coordinator_read(self):
        shared = self.client.get("/events/e1", headers=HEADERS)
        notes = self.client.get("/events/e1/internal-notes", headers=HEADERS)

        self.assertIsNone(shared.json()["internalNotes"])
        self.assertEqual(notes.status_code, 200)
        self.assertEqual(notes.json(), {"eventId": "e1", "internalNotes": "Staff only"})
