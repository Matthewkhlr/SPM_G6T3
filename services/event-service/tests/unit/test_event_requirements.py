from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.event import EventDraftUpsert, OrganiserDraftPatch
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import END, ORGANISER, START, EventCase, draft_payload


class TestEventRequirements(EventCase):
    def test_published_lists_include_layout_facility_and_access(self):
        options = self.service.requirement_options()

        self.assertIn("Theatre", options.layouts)
        self.assertIn("No preference", options.layouts)
        self.assertIn("Projector", options.facilities)
        self.assertIn("Wheelchair accessible", options.accessibility)

    def test_a_draft_saves_location_facilities_access_and_equipment_lines(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        saved = self.service.patch_own_draft(
            created.eventId,
            OrganiserDraftPatch(
                preferredLocation="HarbourFront Centre",
                requiredFacilities=["Projector", "PA system"],
                accessibilityNeeds=["Wheelchair accessible"],
                accessibilityNote="Need a quiet room nearby",
                layoutPreference="Theatre",
                equipmentLines=[
                    {"equipmentId": "eq1", "quantity": 2, "technicalNotes": "HDMI to the lectern"},
                    {"equipmentId": "eq2", "quantity": 1},
                ],
            ),
            "org-1",
        )

        self.assertIn("HarbourFront", saved.preferredLocation)
        self.assertIn("Projector", saved.requiredFacilities)
        self.assertIn("Wheelchair", saved.accessibilityNeeds)
        self.assertIn("quiet room", saved.accessibilityNote)
        self.assertEqual(len(saved.equipmentLines), 2)
        self.assertEqual(saved.equipmentLines[0]["quantity"], 2)
        self.assertNotIn("unitId", saved.equipmentLines[0])

    def test_adding_the_same_equipment_type_again_edits_the_line(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")
        self.service.patch_own_draft(
            created.eventId,
            OrganiserDraftPatch(equipmentLines=[{"equipmentId": "eq1", "quantity": 1, "technicalNotes": "first"}]),
            "org-1",
        )

        again = self.service.patch_own_draft(
            created.eventId,
            OrganiserDraftPatch(equipmentLines=[{"equipmentId": "eq1", "quantity": 3, "technicalNotes": "updated"}]),
            "org-1",
        )

        eq1 = [line for line in again.equipmentLines if line["equipmentId"] == "eq1"]
        self.assertEqual(len(eq1), 1)
        self.assertEqual(eq1[0]["quantity"], 3)
        self.assertIn("updated", eq1[0]["technicalNotes"])

    def test_a_duplicate_type_in_one_save_keeps_the_later_quantity(self):
        created = self.service.create_draft(
            draft_payload(
                equipmentLines=[
                    {"equipmentId": "eq1", "quantity": 1, "technicalNotes": "first"},
                    {"equipmentId": "eq1", "quantity": 4, "technicalNotes": "second"},
                ]
            ),
            "org-1",
            "o1",
        )

        self.assertEqual(len(created.equipmentLines), 1)
        self.assertEqual(created.equipmentLines[0]["quantity"], 4)

    def test_a_string_accessibility_need_is_stored_as_text(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        saved = self.service.patch_own_draft(
            created.eventId,
            OrganiserDraftPatch(accessibilityNeeds="Hearing loop", preferredLocation=None),
            "org-1",
        )

        self.assertEqual(saved.accessibilityNeeds, "Hearing loop")
        self.assertEqual(saved.preferredLocation, "")

    def test_submit_uses_the_fields_already_on_the_draft(self):
        created = self.service.create_draft(draft_payload(eventName="Visible"), "org-1", "o1")
        self.service.patch_own_draft(
            created.eventId,
            OrganiserDraftPatch(
                purpose="Visible to coordinator",
                category="meeting",
                expectedAttendance=10,
                proposedStartAt=START,
                proposedEndAt=END,
                layoutPreference="Theatre",
                requiredFacilities=["Projector"],
                accessibilityNeeds=["Wheelchair accessible"],
                equipmentLines=[{"equipmentId": "eq1", "quantity": 2, "technicalNotes": "Keep HDMI"}],
            ),
            "org-1",
        )

        submitted = self.service.submit_stored_draft(created.eventId, "org-1")

        self.assertEqual(submitted.status, "submitted")
        self.assertIn("Theatre", submitted.layoutPreference)
        self.assertIn("Projector", submitted.requiredFacilities)
        self.assertIn("HDMI", submitted.equipmentLines[0]["technicalNotes"])

    def test_submit_refuses_a_draft_that_is_still_incomplete(self):
        from fastapi import HTTPException

        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.submit_stored_draft(created.eventId, "org-1")

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("expectedAttendance", ctx.exception.detail)

    def test_submit_refuses_an_end_that_is_not_after_the_start(self):
        from fastapi import HTTPException

        created = self.service.create_draft(draft_payload(), "org-1", "o1")
        row = self.service._require_event(created.eventId)
        row.proposedStartAt = END
        row.proposedEndAt = START
        row.expectedAttendance = 2
        self.db.commit()

        with self.assertRaises(HTTPException) as ctx:
            self.service.submit_stored_draft(created.eventId, "org-1")

        self.assertEqual(ctx.exception.status_code, 422)

    def test_a_draft_upsert_can_carry_the_requirement_fields(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        updated = self.service.update_draft(
            created.eventId,
            EventDraftUpsert(
                eventName="Renamed",
                layoutPreference="Banquet",
                preferredLocation="City Hall",
                accessibilityNote="Ramp at the side",
            ),
            "org-1",
        )

        self.assertEqual(updated.layoutPreference, "Banquet")
        self.assertEqual(updated.preferredLocation, "City Hall")
        self.assertEqual(updated.accessibilityNote, "Ramp at the side")


class TestEventRequirementRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.counts = patch("app.services.event_service.registration_count", return_value=0)
        self.organiser = patch("app.routers.event.current_organiser", return_value=ORGANISER)
        self.caller = patch("app.routers.event.resolve_caller", return_value=ORGANISER)
        self.counts.start()
        self.organiser.start()
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        self.organiser.stop()
        self.counts.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_name_only_create_is_a_draft_and_options_are_public(self):
        headers = {"Authorization": "Bearer token"}
        options = self.client.get("/events/requirement-options", headers=headers)
        created = self.client.post("/events", headers=headers, json={"eventName": "AUTO-SPM80"})

        self.assertEqual(options.status_code, 200)
        self.assertTrue(any("Theatre" in layout for layout in options.json()["layouts"]))
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["status"], "draft")

    def test_patch_rejects_a_quantity_that_is_not_a_positive_whole_number(self):
        headers = {"Authorization": "Bearer token"}
        created = self.client.post("/events", headers=headers, json={"eventName": "AUTO-SPM80-qty"})
        event_id = created.json()["eventId"]

        for quantity in (0, -1, 1.5):
            denied = self.client.patch(
                f"/events/{event_id}",
                headers=headers,
                json={"equipmentLines": [{"equipmentId": "eq1", "quantity": quantity}]},
            )
            self.assertEqual(denied.status_code, 422)
            self.assertRegex(denied.text, r"whole|integer|at least 1|quantity")

    def test_an_empty_submit_body_submits_the_saved_draft(self):
        headers = {"Authorization": "Bearer token"}
        created = self.client.post("/events", headers=headers, json={"eventName": "AUTO-SPM80-submit"})
        event_id = created.json()["eventId"]
        self.client.patch(
            f"/events/{event_id}",
            headers=headers,
            json={
                "proposedStartAt": "2026-11-01T09:00:00",
                "proposedEndAt": "2026-11-01T17:00:00",
                "expectedAttendance": 10,
            },
        )

        submitted = self.client.post(f"/events/{event_id}/submit", headers=headers)

        self.assertEqual(submitted.status_code, 200)
        self.assertEqual(submitted.json()["status"], "submitted")

    def test_a_partial_submit_body_is_rejected(self):
        headers = {"Authorization": "Bearer token"}
        created = self.client.post("/events", headers=headers, json={"eventName": "AUTO-SPM80-bad"})

        denied = self.client.post(
            f"/events/{created.json()['eventId']}/submit",
            headers=headers,
            json={"eventName": "Only a name"},
        )

        self.assertEqual(denied.status_code, 422)
