from datetime import datetime, timedelta
from unittest.mock import patch

from app.core.config import settings
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

    def test_queue_sort_by_proposed_date_and_assignment_filter(self):
        insert_event(
            self.db,
            eventId="e-near",
            status="submitted",
            eventName="Near",
            proposedStartAt=datetime(2026, 9, 1, 9),
            submittedAt=datetime.utcnow() - timedelta(hours=1),
        )
        insert_event(
            self.db,
            eventId="e-far",
            status="submitted",
            eventName="Far",
            coordinatorId="coord-1",
            proposedStartAt=datetime(2026, 12, 1, 9),
            submittedAt=datetime.utcnow() - timedelta(hours=2),
        )

        by_date = self.service.list_submission_queue(sort="proposedStartAt")
        self.assertEqual([row.eventId for row in by_date], ["e-near", "e-far"])

        mine = self.service.list_submission_queue(assigned_to="coord-1")
        self.assertEqual([row.eventId for row in mine], ["e-far"])

    def test_the_queue_keeps_only_review_statuses_and_an_unknown_assignee_is_empty(self):
        kept = ("submitted", "under review", "changes requested")
        dropped = ("draft", "confirmed", "rejected", "completed", "cancelled", "discarded")
        for index, status in enumerate((*kept, *dropped)):
            insert_event(
                self.db,
                eventId=f"e-{index}",
                status=status,
                submittedAt=datetime(2026, 1, 1) + timedelta(hours=index),
            )

        queue = [row.eventId for row in self.service.list_submission_queue()]

        self.assertEqual(queue, ["e-0", "e-1", "e-2"])
        self.assertEqual(self.service.list_submission_queue(assigned_to="nobody"), [])

    def test_a_proposed_date_is_near_on_the_threshold_and_not_one_second_later(self):
        now = datetime(2026, 10, 3, 12, 0)
        limit = timedelta(days=settings.event_proposed_date_near_days)
        starts = {
            "e-none": None,
            "e-now": now,
            "e-inside": now + limit - timedelta(seconds=1),
            "e-on": now + limit,
            "e-past-limit": now + limit + timedelta(seconds=1),
            "e-already": now - timedelta(days=1),
        }
        for event_id, start in starts.items():
            insert_event(self.db, eventId=event_id, status="submitted", proposedStartAt=start)

        with patch("app.services.event_service.datetime") as clock:
            clock.utcnow.return_value = now
            flags = {row.eventId: row.dateNear for row in self.service.list_submission_queue()}

        self.assertFalse(flags["e-none"])
        self.assertTrue(flags["e-now"])
        self.assertTrue(flags["e-inside"])
        self.assertTrue(flags["e-on"])
        self.assertFalse(flags["e-past-limit"])
        self.assertTrue(flags["e-already"])

    def test_an_event_ending_at_this_instant_is_upcoming_and_one_microsecond_earlier_is_not(self):
        now = datetime(2026, 10, 3, 12, 0)
        insert_event(
            self.db,
            eventId="e-now",
            status="confirmed",
            proposedStartAt=now - timedelta(hours=2),
            proposedEndAt=now,
        )
        insert_event(
            self.db,
            eventId="e-just-ended",
            status="confirmed",
            proposedStartAt=now - timedelta(hours=3),
            proposedEndAt=now - timedelta(microseconds=1),
        )
        insert_event(
            self.db,
            eventId="e-later",
            status="confirmed",
            proposedStartAt=now + timedelta(days=2),
            proposedEndAt=now + timedelta(days=2, hours=1),
        )
        insert_event(
            self.db,
            eventId="e-cancelled",
            status="cancelled",
            proposedStartAt=now + timedelta(hours=1),
            proposedEndAt=now + timedelta(hours=2),
        )

        with patch("app.services.event_service.datetime") as clock:
            clock.utcnow.return_value = now
            upcoming = [row.eventId for row in self.service.list_upcoming_events()]

        self.assertEqual(upcoming, ["e-now", "e-later"])
