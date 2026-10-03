import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.event_assignment import EventAssignment
from app.models.event_status_history import EventStatusHistory
from app.orchestration import clients
from app.schemas.event import EventAssignmentCreate
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden, service_unavailable
from tests.unit.support import COORDINATOR, EventCase, insert_event

DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "coord-2", "userName": "Cara Ng", "email": "cara@connectsphere.com", "role": "coordinator"},
    {"userId": "venue-1", "userName": "Carol", "email": "carol@connectsphere.com", "role": "venue"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
]
ORGANISER = {"userId": "org-1", "role": "organiser", "organisationId": "o1"}


class AssignmentCase(EventCase):
    def setUp(self):
        super().setUp()
        self.patches = {
            "names": patch("app.services.event_service.organisation_names", return_value={}),
            "users": patch("app.services.event_service.list_users", return_value=DIRECTORY),
            "notify": patch("app.services.event_service.send_notification", return_value=True),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        super().tearDown()

    def event(self, event_id="e1", status="submitted", **overrides):
        return insert_event(self.db, eventId=event_id, status=status, eventName="Summit", **overrides)

    def assign(self, coordinator_id="coord-1", event_id="e1", assigned_by="coord-1"):
        return self.service.assign_coordinator(
            event_id, EventAssignmentCreate(coordinatorId=coordinator_id), assigned_by, "Bearer token"
        )


class TestAssigning(AssignmentCase):
    def test_a_coordinator_can_assign_a_submitted_event_to_themselves(self):
        self.event()

        assignment = self.assign()

        self.assertEqual((assignment.coordinatorId, assignment.assignedBy), ("coord-1", "coord-1"))
        self.assertEqual(self.service.get_event("e1").coordinatorId, "coord-1")

    def test_assigning_a_submitted_event_moves_it_to_under_review(self):
        self.event()

        self.assign(coordinator_id="coord-2")

        self.assertEqual(self.service.get_event("e1").status, "under review")
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual((history.fromStatus, history.toStatus, history.changedBy), ("submitted", "under review", "coord-1"))
        self.assertEqual(history.note, "Assigned to Cara Ng")

    def test_reassigning_keeps_the_events_status(self):
        self.event(status="confirmed", coordinatorId="coord-1")

        self.assign(coordinator_id="coord-2")

        stored = self.service.get_event("e1")
        self.assertEqual((stored.coordinatorId, stored.status), ("coord-2", "confirmed"))
        self.assertEqual(self.db.query(EventStatusHistory).count(), 0)

    def test_there_is_no_workload_limit(self):
        for index in range(25):
            self.event(event_id=f"busy-{index}", status="planning", coordinatorId="coord-2")
        self.event()

        self.assertEqual(self.assign(coordinator_id="coord-2").coordinatorId, "coord-2")

    def test_only_an_event_coordinator_can_be_assigned(self):
        self.event()
        for user_id in ("venue-1", "org-1", "nobody"):
            with self.assertRaises(HTTPException) as ctx:
                self.assign(coordinator_id=user_id)

            self.assertEqual(ctx.exception.status_code, 422, user_id)
        self.assertEqual(self.db.query(EventAssignment).count(), 0)
        self.assertEqual(self.service.get_event("e1").status, "submitted")
        self.mocks["notify"].assert_not_called()

    def test_finished_events_and_drafts_cannot_be_assigned(self):
        for index, status in enumerate(("completed", "cancelled", "rejected", "draft", "discarded")):
            self.event(event_id=f"closed-{index}", status=status)

            with self.assertRaises(HTTPException) as ctx:
                self.assign(event_id=f"closed-{index}")

            self.assertEqual(ctx.exception.status_code, 409, status)
        self.mocks["users"].assert_not_called()

    def test_an_unreachable_user_directory_saves_nothing(self):
        self.event()
        self.mocks["users"].side_effect = service_unavailable("down")

        with self.assertRaises(HTTPException) as ctx:
            self.assign()

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(self.db.query(EventAssignment).count(), 0)
        self.assertIsNone(self.service.get_event("e1").coordinatorId)


class TestAssignmentNotifications(AssignmentCase):
    def test_the_new_coordinator_and_the_organiser_are_notified(self):
        self.event()

        self.assign(coordinator_id="coord-2")

        calls = self.mocks["notify"].call_args_list
        self.assertEqual([call.args[0] for call in calls], ["cara@connectsphere.com", "amy@apex.com"])
        self.assertIn("Summit", calls[0].args[1])
        self.assertIn("Cara Ng", calls[1].args[2])
        self.assertIn("cara@connectsphere.com", calls[1].args[2])
        self.assertEqual(calls[0].args[3], "Bearer token")

    def test_an_organiser_missing_from_the_directory_is_skipped(self):
        self.event(organiserId="gone")

        self.assign()

        self.assertEqual([call.args[0] for call in self.mocks["notify"].call_args_list], ["ben@connectsphere.com"])

    def test_a_failed_notification_does_not_undo_the_assignment(self):
        self.event()
        self.mocks["notify"].return_value = False

        self.assign()

        self.assertEqual(self.service.get_event("e1").coordinatorId, "coord-1")


class TestCandidatesAndLog(AssignmentCase):
    def test_candidates_are_coordinators_with_their_active_event_counts(self):
        self.event(event_id="a", status="planning", coordinatorId="coord-2")
        self.event(event_id="b", status="under review", coordinatorId="coord-2")
        self.event(event_id="c", status="completed", coordinatorId="coord-2")
        self.event(event_id="d", status="cancelled", coordinatorId="coord-2")
        self.event(event_id="e", status="submitted")

        candidates = self.service.list_coordinator_candidates("Bearer token")

        self.assertEqual(
            [(row.userId, row.name, row.email, row.activeEventCount) for row in candidates],
            [("coord-1", "Ben Lee", "ben@connectsphere.com", 0), ("coord-2", "Cara Ng", "cara@connectsphere.com", 2)],
        )

    def test_the_activity_log_records_who_assigned_whom_and_when(self):
        self.event()
        self.assign(coordinator_id="coord-1")
        # Back-to-back calls can share a clock tick; the reassignment happens later.
        earlier = datetime(2026, 9, 1, 9)
        self.db.query(EventAssignment).one().assignedAt = earlier
        self.db.query(EventStatusHistory).one().createdAt = earlier
        self.db.commit()
        self.assign(coordinator_id="coord-2", assigned_by="coord-1")

        log = self.service.get_activity_log("e1")

        self.assertEqual([entry.kind for entry in log], ["assignment", "status", "assignment"])
        first, status, second = log
        self.assertEqual((first.field, first.oldValue, first.newValue, first.changedBy), ("coordinatorId", None, "coord-1", "coord-1"))
        self.assertEqual(first.createdAt, status.createdAt)
        self.assertEqual(status.toStatus, "under review")
        self.assertEqual((second.oldValue, second.newValue), ("coord-1", "coord-2"))

    def test_a_request_under_review_can_still_be_approved_or_rejected(self):
        self.event(event_id="a", status="under review", coordinatorId="coord-1")
        self.event(event_id="b", status="under review")

        self.assertEqual(self.service.approve_event("a", "coord-1").status, "planning")
        self.assertEqual(self.service.reject_event("b", "coord-1", "Dates clash").status, "rejected")
        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_event("a", "coord-1")
        self.assertEqual(ctx.exception.status_code, 409)


class TestEventCoordinatorContact(AssignmentCase):
    def test_the_organiser_sees_their_coordinators_name_and_email(self):
        self.event(coordinatorId="coord-1")

        contact = self.service.get_event_coordinator("e1", ORGANISER, "Bearer token")

        self.assertEqual(
            (contact.coordinatorId, contact.name, contact.email), ("coord-1", "Ben Lee", "ben@connectsphere.com")
        )

    def test_a_colleague_in_the_same_organisation_and_staff_can_see_it(self):
        self.event(coordinatorId="coord-1")
        colleague = {"userId": "org-9", "role": "organiser", "organisationId": "o1"}

        for caller in (colleague, {"userId": "v", "role": "venue"}, {"userId": "t", "role": "techsupport"}, COORDINATOR):
            self.assertEqual(self.service.get_event_coordinator("e1", caller).name, "Ben Lee")

    def test_other_organisations_and_attendees_cannot_see_it(self):
        self.event(coordinatorId="coord-1")
        callers = [
            {"userId": "org-9", "role": "organiser", "organisationId": "o2"},
            {"userId": "org-9", "role": "organiser", "organisationId": None},
            {"userId": "att-1", "role": "attendee"},
        ]
        for caller in callers:
            with self.assertRaises(HTTPException) as ctx:
                self.service.get_event_coordinator("e1", caller)

            self.assertEqual(ctx.exception.status_code, 403, caller)

    def test_an_unassigned_event_has_no_coordinator(self):
        self.event()

        contact = self.service.get_event_coordinator("e1", ORGANISER)

        self.assertEqual((contact.coordinatorId, contact.name, contact.email), (None, None, None))
        self.mocks["users"].assert_not_called()

    def test_a_coordinator_missing_from_the_directory_keeps_their_id(self):
        self.event(coordinatorId="gone")

        contact = self.service.get_event_coordinator("e1", ORGANISER)

        self.assertEqual((contact.coordinatorId, contact.name, contact.email), ("gone", None, None))


def reply(status_code, body=None):
    response = MagicMock(status_code=status_code)
    response.json.return_value = body
    return response


class TestAssignmentClients(unittest.TestCase):
    def test_list_users_returns_the_directory(self):
        with patch.object(clients._user_directory_client, "get", return_value=reply(200, DIRECTORY)) as get:
            users = clients.list_users("Bearer token")

        self.assertEqual(users, DIRECTORY)
        self.assertTrue(get.call_args.args[0].endswith("/users"))
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_list_users_is_a_503_when_user_service_fails(self):
        for outcome in ({"return_value": reply(500)}, {"side_effect": httpx.ConnectError("down")}):
            with patch.object(clients._user_directory_client, "get", **outcome):
                with self.assertRaises(HTTPException) as ctx:
                    clients.list_users(None)

            self.assertEqual(ctx.exception.status_code, 503)

    def test_send_notification_posts_an_email(self):
        client = MagicMock()
        client.__enter__.return_value.post.return_value = reply(200, {"status": "queued"})
        with patch("app.orchestration.clients.httpx.Client", MagicMock(return_value=client)):
            sent = clients.send_notification("ben@connectsphere.com", "Subject", "Body", "Bearer token")

        self.assertTrue(sent)
        post = client.__enter__.return_value.post
        self.assertTrue(post.call_args.args[0].endswith("/notifications"))
        self.assertEqual(post.call_args.kwargs["json"], {"to": "ben@connectsphere.com", "subject": "Subject", "body": "Body"})

    def test_send_notification_reports_a_failure_without_raising(self):
        client = MagicMock()
        client.__enter__.return_value.post.return_value = reply(503)
        with patch("app.orchestration.clients.httpx.Client", MagicMock(return_value=client)):
            self.assertFalse(clients.send_notification("a@b.com", "S", "B", None))
        with patch("app.orchestration.clients.httpx.Client", side_effect=httpx.ConnectError("down")):
            self.assertFalse(clients.send_notification("a@b.com", "S", "B", None))


class TestAssignmentRoutes(AssignmentCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.event.resolve_caller", return_value=COORDINATOR)
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_coordinators_list_candidates_and_assign(self):
        self.event()

        candidates = self.client.get("/events/coordinators", headers=self.headers)
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})
        assigned = self.client.post("/events/e1/assign-coordinator", headers=self.headers, json={"coordinatorId": "coord-2"})
        refused = self.client.post("/events/e1/assign-coordinator", headers=self.headers, json={"coordinatorId": "venue-1"})

        self.assertEqual(candidates.status_code, 200)
        self.assertEqual([row["userId"] for row in candidates.json()], ["coord-1", "coord-2"])
        self.assertEqual(assigned.status_code, 201)
        self.assertEqual(assigned.json()["assignedBy"], "coord-1")
        self.assertEqual(self.client.get("/events/e1", headers=self.headers).json()["status"], "under review")
        self.assertEqual(refused.status_code, 422)

    def test_other_roles_cannot_assign_or_list_candidates(self):
        self.event()
        self.caller_mock.side_effect = forbidden()

        self.assertEqual(self.client.get("/events/coordinators", headers=self.headers).status_code, 403)
        self.assertEqual(
            self.client.post("/events/e1/assign-coordinator", headers=self.headers, json={"coordinatorId": "coord-1"}).status_code,
            403,
        )

    def test_the_coordinator_contact_route_checks_the_caller(self):
        self.event(coordinatorId="coord-1")

        self.caller_mock.return_value = ORGANISER
        shown = self.client.get("/events/e1/coordinator", headers=self.headers)
        self.caller_mock.return_value = {"userId": "att-1", "role": "attendee"}
        hidden = self.client.get("/events/e1/coordinator", headers=self.headers)

        self.assertEqual(shown.status_code, 200)
        self.assertEqual(shown.json()["name"], "Ben Lee")
        self.assertNotIn("allowed_roles", self.caller_mock.call_args.kwargs)
        self.assertEqual(hidden.status_code, 403)
