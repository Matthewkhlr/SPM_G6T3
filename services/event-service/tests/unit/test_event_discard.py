from fastapi import HTTPException

from tests.unit.support import EventCase, draft_payload, event_create


class TestEventDiscard(EventCase):
    def test_discard_draft_marks_it_discarded(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        discarded = self.service.discard_draft(created.eventId, "org-1")

        self.assertEqual(discarded.status, "discarded")

    def test_discard_draft_rejects_another_organiser_and_a_submitted_event(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")
        with self.assertRaises(HTTPException) as ctx:
            self.service.discard_draft(created.eventId, "someone-else")
        self.assertEqual(ctx.exception.status_code, 403)

        submitted = self.service.create_event(event_create(), "org-1", "o1")
        with self.assertRaises(HTTPException) as ctx:
            self.service.discard_draft(submitted.eventId, "org-1")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_discard_missing_event_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.discard_draft("missing", "org-1")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_activity_log_is_404_when_the_event_is_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_activity_log("missing")

        self.assertEqual(ctx.exception.status_code, 404)
