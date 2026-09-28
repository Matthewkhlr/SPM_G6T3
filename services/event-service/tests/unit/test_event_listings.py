from datetime import datetime, timedelta

from tests.unit.support import EventCase, draft_payload, event_create, insert_event


class TestEventListings(EventCase):
    def test_lists_filter_by_status_and_owner(self):
        submitted = self.service.create_event(event_create(eventName="Submitted"), "org-1", "o1")
        draft = self.service.create_draft(draft_payload(), "org-1", "o1")
        discarded = self.service.create_draft(draft_payload(eventName="Gone"), "org-1", "o1")
        self.service.discard_draft(discarded.eventId, "org-1")
        insert_event(self.db, eventId="e-confirmed", status="confirmed", eventName="Confirmed")
        insert_event(
            self.db,
            eventId="e-rejected",
            status="rejected",
            eventName="Rejected",
            submittedAt=datetime.utcnow() - timedelta(days=2),
        )
        insert_event(self.db, eventId="e-old", status="submitted", eventName="Waiting", submittedAt=datetime(2026, 1, 1))
        insert_event(
            self.db,
            eventId="e-completed",
            status="completed",
            eventName="Done",
            proposedEndAt=datetime(2020, 1, 1),
        )
        insert_event(self.db, eventId="e-other", status="draft", organiserId="org-2", eventName="Other draft")

        visible = {row.eventId for row in self.service.list_events()}
        self.assertIn(submitted.eventId, visible)
        self.assertNotIn(draft.eventId, visible)
        self.assertNotIn(discarded.eventId, visible)

        all_ids = {row.eventId for row in self.service.list_all_events()}
        self.assertIn(submitted.eventId, all_ids)
        self.assertNotIn("e-rejected", all_ids)
        self.assertNotIn(draft.eventId, all_ids)

        confirmed = self.service.list_confirmed_events()
        self.assertEqual([row.eventId for row in confirmed], ["e-confirmed"])

        upcoming = {row.eventId for row in self.service.list_upcoming_events()}
        self.assertIn("e-confirmed", upcoming)
        self.assertNotIn("e-completed", upcoming)
        self.assertNotIn("e-rejected", upcoming)

        queue = self.service.list_submission_queue()
        self.assertEqual(queue[0].eventId, "e-old")

        my_drafts = {row.eventId for row in self.service.list_my_drafts("org-1")}
        self.assertEqual(my_drafts, {draft.eventId})

        mine = {row.eventId for row in self.service.list_my_events("org-1")}
        self.assertIn(submitted.eventId, mine)
        self.assertNotIn(discarded.eventId, mine)
