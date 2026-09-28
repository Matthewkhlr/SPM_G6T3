from fastapi import HTTPException

from tests.unit.support import EventCase, draft_payload, event_create


class TestEventDrafts(EventCase):
    def test_create_draft_defaults_a_blank_attendance(self):
        created = self.service.create_draft(draft_payload(), "org-1", None)

        self.assertEqual(created.status, "draft")
        self.assertEqual(created.expectedAttendance, 0)

    def test_create_draft_keeps_a_supplied_attendance(self):
        created = self.service.create_draft(draft_payload(expectedAttendance=12), "org-1", "o1")

        self.assertEqual(created.expectedAttendance, 12)

    def test_update_draft_saves_the_new_name(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        updated = self.service.update_draft(created.eventId, draft_payload(eventName="Renamed"), "org-1")

        self.assertEqual(updated.eventName, "Renamed")

    def test_update_draft_rejects_another_organiser(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.update_draft(created.eventId, draft_payload(), "someone-else")

        self.assertEqual(ctx.exception.status_code, 403)

    def test_update_draft_conflicts_once_the_event_is_submitted(self):
        created = self.service.create_event(event_create(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.update_draft(created.eventId, draft_payload(), "org-1")

        self.assertEqual(ctx.exception.status_code, 409)

    def test_submit_draft_records_the_status_change(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        submitted = self.service.submit_draft(created.eventId, event_create(), "org-1")
        log = self.service.get_activity_log(created.eventId)

        self.assertEqual(submitted.status, "submitted")
        self.assertEqual(log[0].fromStatus, "draft")
        self.assertEqual(log[0].toStatus, "submitted")
        self.assertEqual(log[0].note, "")

    def test_submit_draft_rejects_another_organiser_and_a_submitted_event(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")
        with self.assertRaises(HTTPException) as ctx:
            self.service.submit_draft(created.eventId, event_create(), "someone-else")
        self.assertEqual(ctx.exception.status_code, 403)

        submitted = self.service.create_event(event_create(), "org-1", "o1")
        with self.assertRaises(HTTPException) as ctx:
            self.service.submit_draft(submitted.eventId, event_create(), "org-1")
        self.assertEqual(ctx.exception.status_code, 409)
