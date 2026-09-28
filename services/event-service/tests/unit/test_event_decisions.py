from fastapi import HTTPException

from app.schemas.event import EventAssignmentCreate
from tests.unit.support import EventCase, draft_payload, event_create


class TestEventDecisions(EventCase):
    def test_missing_event_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_event("missing")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_assign_coordinator_stores_the_assignment(self):
        created = self.service.create_event(event_create(), "org-1", "o1")

        assignment = self.service.assign_coordinator(
            created.eventId, EventAssignmentCreate(coordinatorId="coord-1"), "coord-1"
        )

        self.assertEqual(assignment.coordinatorId, "coord-1")
        self.assertEqual(assignment.assignedBy, "coord-1")
        self.assertEqual(self.service.get_event(created.eventId).status, "submitted")

    def test_assign_coordinator_is_404_when_the_event_is_missing(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.assign_coordinator("missing", EventAssignmentCreate(coordinatorId="coord-1"), "coord-1")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_approve_event_moves_a_submitted_event_to_approved(self):
        created = self.service.create_event(event_create(), "org-1", "o1")

        approved = self.service.approve_event(created.eventId, "coord-1")

        self.assertEqual(approved.status, "approved")

    def test_approve_event_conflicts_when_it_is_not_submitted(self):
        created = self.service.create_draft(draft_payload(), "org-1", "o1")

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_event(created.eventId, "coord-1")

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service.get_event(created.eventId).status, "draft")

    def test_reject_event_stores_the_reason(self):
        created = self.service.create_event(event_create(), "org-1", "o1")

        rejected = self.service.reject_event(created.eventId, "coord-1", "Dates clash")
        log = self.service.get_activity_log(created.eventId)

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(log[0].note, "Dates clash")
        self.assertEqual(log[0].changedBy, "coord-1")
