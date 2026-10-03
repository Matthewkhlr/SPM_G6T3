from datetime import timedelta
from unittest.mock import patch

from fastapi import HTTPException

from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.services.event_service import EventService
from shared.testing.cases import ServiceTestCase
from tests.unit.support import END, START, draft_payload, event_create


class TestEventLifecycle(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.counts = patch("app.services.event_service.registration_count", return_value=0)
        self.counts.start()
        self.service = EventService(
            self.db, EventDAO(self.db), EventAssignmentDAO(self.db), EventStatusHistoryDAO(self.db)
        )
        self.event = self.service.create_event(event_create(), "org-1", "o1")

    def tearDown(self):
        self.counts.stop()
        super().tearDown()

    def test_confirm_moves_an_approved_event_to_confirmed(self):
        self.assertTrue(hasattr(self.service, "confirm_event"), "confirm_event is not implemented")
        self.service.approve_event(self.event.eventId, "coord-1")

        confirmed = self.service.confirm_event(self.event.eventId, "coord-1")

        self.assertEqual(confirmed.status, "confirmed")

    def test_confirm_refuses_an_event_that_is_still_submitted(self):
        self.assertTrue(hasattr(self.service, "confirm_event"), "confirm_event is not implemented")

        with self.assertRaises(HTTPException) as ctx:
            self.service.confirm_event(self.event.eventId, "coord-1")

        self.assertEqual(ctx.exception.status_code, 409)

    def test_complete_moves_a_confirmed_event_to_completed(self):
        self.assertTrue(hasattr(self.service, "complete_event"), "complete_event is not implemented")
        self.service.approve_event(self.event.eventId, "coord-1")
        self.service.confirm_event(self.event.eventId, "coord-1")

        completed = self.service.complete_event(self.event.eventId, "coord-1")

        self.assertEqual(completed.status, "completed")

    def test_cancel_requires_a_reason_and_is_terminal(self):
        self.assertTrue(hasattr(self.service, "cancel_event"), "cancel_event is not implemented")

        with self.assertRaises(HTTPException) as ctx:
            self.service.cancel_event(self.event.eventId, "org-1", "")
        self.assertEqual(ctx.exception.status_code, 409)

        cancelled = self.service.cancel_event(self.event.eventId, "org-1", "Client postponed")
        self.assertEqual(cancelled.status, "cancelled")
        log = self.service.get_activity_log(self.event.eventId)
        self.assertEqual(log[-1].toStatus, "cancelled")
        self.assertIn("Client postponed", log[-1].note)

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_event(self.event.eventId, "coord-1")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_a_draft_cannot_take_a_change_request(self):
        self.assertTrue(hasattr(self.service, "request_change"), "request_change is not implemented")
        draft = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.request_change(draft.eventId, "org-1", {"eventName": "New"}, "Rename")

        self.assertIn(ctx.exception.status_code, (403, 409))

    def test_only_one_change_request_can_be_pending(self):
        self.assertTrue(hasattr(self.service, "request_change"), "request_change is not implemented")
        self.service.approve_event(self.event.eventId, "coord-1")
        self.service.request_change(self.event.eventId, "org-1", {"eventName": "Summit 2"}, "Rename")

        with self.assertRaises(HTTPException) as ctx:
            self.service.request_change(self.event.eventId, "org-1", {"purpose": "Other"}, "Retitle")

        self.assertEqual(ctx.exception.status_code, 409)

    def test_reschedule_records_the_old_and_new_period(self):
        self.assertTrue(hasattr(self.service, "reschedule"), "reschedule is not implemented")
        self.service.approve_event(self.event.eventId, "coord-1")
        new_start = START + timedelta(days=7)
        new_end = END + timedelta(days=7)

        moved = self.service.reschedule(self.event.eventId, "coord-1", new_start, new_end, "Speaker moved")

        self.assertEqual(moved.proposedStartAt, new_start)
        self.assertEqual(moved.proposedEndAt, new_end)
        log = self.service.get_activity_log(self.event.eventId)
        self.assertIn("Speaker moved", log[-1].note)
