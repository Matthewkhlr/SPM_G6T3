import unittest
from datetime import datetime, timedelta

from pydantic import ValidationError

from app.schemas.event import EventAssignmentCreate, EventDecision
from tests.unit.support import START, draft_payload, event_create


class TestEventSchema(unittest.TestCase):
    def test_create_rejects_an_end_that_is_not_after_the_start(self):
        with self.assertRaises(ValidationError):
            event_create(proposedEndAt=START)

    def test_create_rejects_a_registration_window_that_closes_too_early(self):
        with self.assertRaises(ValidationError):
            event_create(registrationOpensAt=datetime(2026, 10, 2), registrationClosesAt=datetime(2026, 10, 1))

    def test_draft_rejects_an_end_that_is_not_after_the_start(self):
        with self.assertRaises(ValidationError):
            draft_payload(proposedStartAt=datetime(2026, 10, 6, 17, 0), proposedEndAt=START)

    def test_draft_allows_a_missing_schedule(self):
        draft = draft_payload(proposedStartAt=START, proposedEndAt=None)

        self.assertEqual(draft.eventName, "Draft summit")
        self.assertIsNone(draft.proposedEndAt)

    def test_a_registration_window_that_opens_and_closes_together_is_rejected(self):
        same = datetime(2026, 10, 1, 0, 0)

        with self.assertRaises(ValidationError):
            event_create(registrationOpensAt=same, registrationClosesAt=same)

        accepted = event_create(registrationOpensAt=same, registrationClosesAt=same + timedelta(seconds=1))
        self.assertEqual(accepted.registrationClosesAt, same + timedelta(seconds=1))

    def test_a_draft_schedule_must_be_strictly_increasing(self):
        with self.assertRaises(ValidationError):
            draft_payload(proposedStartAt=START, proposedEndAt=START)

        accepted = draft_payload(proposedStartAt=START, proposedEndAt=START + timedelta(seconds=1))
        self.assertEqual(accepted.proposedEndAt, START + timedelta(seconds=1))

    def test_event_name_and_attendance_accept_their_limits(self):
        shortest = event_create(eventName="A", expectedAttendance=0, capacity=0)
        longest = event_create(eventName="A" * 255)

        self.assertEqual(shortest.eventName, "A")
        self.assertEqual(shortest.expectedAttendance, 0)
        self.assertEqual(shortest.capacity, 0)
        self.assertEqual(len(longest.eventName), 255)

        with self.assertRaises(ValidationError):
            event_create(eventName="")
        with self.assertRaises(ValidationError):
            event_create(eventName="A" * 256)
        with self.assertRaises(ValidationError):
            event_create(expectedAttendance=-1)
        with self.assertRaises(ValidationError):
            event_create(capacity=-1)

    def test_decision_and_assignment_models_keep_optional_fields(self):
        decision = EventDecision()
        assignment = EventAssignmentCreate(coordinatorId="coord-1")

        self.assertIsNone(decision.reason)
        self.assertEqual(assignment.coordinatorId, "coord-1")
