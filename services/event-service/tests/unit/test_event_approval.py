from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.event_review import EventReview
from app.models.event_status_history import EventStatusHistory
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import COORDINATOR, ORGANISER, EventCase, insert_event

DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
]
HEADERS = {"Authorization": "Bearer token"}


class ApprovalCase(EventCase):
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

    def event(self, status="under review", coordinatorId="coord-1", **overrides):
        return insert_event(self.db, eventId="e1", eventName="Summit", status=status, coordinatorId=coordinatorId, **overrides)

    def approve(self, coordinator_id="coord-1", note="", confirm=False):
        return self.service.approve_event("e1", coordinator_id, note, confirm, "Bearer token")

    def refused(self, **kwargs) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            self.approve(**kwargs)
        return ctx.exception


class TestApproving(ApprovalCase):
    """AC1 and AC2."""

    def test_the_assigned_coordinator_approves_a_request_under_review_with_a_note(self):
        self.event()

        approved = self.approve(note="Ready for planning")

        self.assertEqual((approved.status, approved.decision, approved.decisionNote), ("planning", "approved", "Ready for planning"))
        self.assertEqual(self.service.get_event("e1").status, "planning")

    def test_the_note_is_optional(self):
        self.event()

        self.assertEqual(self.approve().decisionNote, "")
        self.assertEqual(self.db.query(EventReview).one().comment, "")

    def test_a_blank_note_is_stored_as_no_note(self):
        self.event()

        self.assertEqual(self.approve(note="   ").decisionNote, "")

    def test_approval_records_the_decision_the_decider_and_the_time(self):
        self.event()
        before = datetime.utcnow()

        approved = self.approve(note="Taken on")

        review = self.db.query(EventReview).one()
        self.assertEqual((review.action, review.reviewerId, review.comment), ("approve", "coord-1", "Taken on"))
        self.assertEqual((approved.decidedBy, approved.decidedAt), ("coord-1", review.createdAt))
        self.assertGreaterEqual(review.createdAt, before)
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual(
            (history.fromStatus, history.toStatus, history.changedBy, history.createdAt),
            ("under review", "planning", "coord-1", review.createdAt),
        )
        log = self.service.get_activity_log("e1")
        self.assertEqual(log[-1].toStatus, "planning")
        # The note is for the organiser; attendees can read the activity log.
        self.assertNotIn("Taken on", str(log))

    def test_another_coordinator_cannot_approve(self):
        self.event()

        error = self.refused(coordinator_id="coord-2")

        self.assertEqual(error.status_code, 403)
        self.assertEqual(self.service.get_event("e1").status, "under review")
        self.assertEqual(self.db.query(EventReview).count(), 0)

    def test_only_a_request_under_review_can_be_approved(self):
        for index, status in enumerate(("submitted", "planning", "confirmed", "rejected", "cancelled")):
            insert_event(self.db, eventId=f"e-{index}", status=status, coordinatorId="coord-1")
            with self.subTest(status=status), self.assertRaises(HTTPException) as ctx:
                self.service.approve_event(f"e-{index}", "coord-1")
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertEqual(self.service.get_event(f"e-{index}").status, status)
        self.assertEqual(self.db.query(EventReview).count(), 0)

    def test_a_missing_event_is_404(self):
        self.assertEqual(self.refused().status_code, 404)


class TestOrganiserIsTold(ApprovalCase):
    """AC3."""

    def test_the_organiser_is_emailed_the_approval_and_the_note(self):
        self.event()

        self.approve(note="Taken on")

        to, subject, body, authorization = self.mocks["notify"].call_args.args
        self.assertEqual((to, subject, authorization), ("amy@apex.com", "Summit has been approved", "Bearer token"))
        self.assertIn("taken it on", body)
        self.assertIn("Note from your coordinator: Taken on", body)

    def test_without_a_note_the_email_has_no_note(self):
        self.event()

        self.approve()

        self.assertNotIn("Note from", self.mocks["notify"].call_args.args[2])

    def test_an_unreachable_directory_does_not_undo_the_approval(self):
        self.mocks["users"].side_effect = service_unavailable("down")
        self.event()

        self.assertEqual(self.approve().status, "planning")
        self.assertEqual(self.service.get_event("e1").status, "planning")
        self.mocks["notify"].assert_not_called()

    def test_an_organiser_missing_from_the_directory_is_not_emailed(self):
        self.mocks["users"].return_value = DIRECTORY[:1]
        self.event()

        self.assertEqual(self.approve().status, "planning")
        self.mocks["notify"].assert_not_called()

    def test_the_organiser_sees_the_outcome_and_the_note_on_their_event(self):
        self.event()
        approved = self.approve(note="Taken on")

        decision = self.service.get_event_decision("e1", ORGANISER)

        self.assertEqual(
            (decision.decision, decision.decisionNote, decision.decidedBy, decision.decidedAt),
            ("approved", "Taken on", "coord-1", approved.decidedAt),
        )

    def test_colleagues_and_staff_see_the_decision_but_other_organisations_and_attendees_do_not(self):
        self.event()
        self.approve()

        colleague = {"userId": "org-2", "organisationId": "o1", "role": "organiser"}
        self.assertEqual(self.service.get_event_decision("e1", colleague).decision, "approved")
        self.assertEqual(self.service.get_event_decision("e1", COORDINATOR).decision, "approved")
        for caller in (
            {"userId": "org-9", "organisationId": "o9", "role": "organiser"},
            {"userId": "att-1", "role": "attendee"},
        ):
            with self.subTest(role=caller["role"]), self.assertRaises(HTTPException) as ctx:
                self.service.get_event_decision("e1", caller)
            self.assertEqual(ctx.exception.status_code, 403)

    def test_before_any_decision_everything_is_null_and_a_clarification_is_not_a_decision(self):
        self.event()
        self.db.add(
            EventReview(reviewId="rv-1", eventId="e1", reviewerId="coord-1", action="request_clarification", comment="Attendance?")
        )
        self.db.commit()

        decision = self.service.get_event_decision("e1", ORGANISER)

        self.assertEqual((decision.eventId, decision.decision, decision.decisionNote, decision.decidedAt), ("e1", None, None, None))

    def test_the_latest_decision_is_shown(self):
        self.event()
        now = datetime.utcnow()
        self.db.add_all(
            [
                EventReview(reviewId="rv-1", eventId="e1", reviewerId="coord-1", action="approve", comment="", createdAt=now - timedelta(days=1)),
                EventReview(reviewId="rv-2", eventId="e1", reviewerId="coord-1", action="reject", comment="Dates clash", createdAt=now),
            ]
        )
        self.db.commit()

        decision = self.service.get_event_decision("e1", ORGANISER)

        self.assertEqual((decision.decision, decision.decisionNote), ("rejected", "Dates clash"))


class TestOpenClarifications(ApprovalCase):
    """AC4."""

    def clarification(self, status="open"):
        self.db.add(
            EventReview(
                reviewId=f"rv-{status}", eventId="e1", reviewerId="coord-1", action="request_clarification",
                comment="Attendance?", status=status,
            )
        )
        self.db.commit()

    def test_a_request_with_only_resolved_clarifications_has_none_open(self):
        self.event()
        self.clarification(status="resolved")

        self.assertFalse(self.service.get_event("e1").hasOpenClarifications)
        self.assertEqual(self.approve().status, "planning")

    def test_approving_with_open_clarifications_warns_and_saves_nothing(self):
        self.event(status="changes requested")
        self.clarification()
        self.assertTrue(self.service.get_event("e1").hasOpenClarifications)

        error = self.refused()

        self.assertEqual(error.status_code, 409)
        self.assertTrue(error.detail["requiresConfirmation"])
        self.assertTrue(error.detail["openClarifications"])
        self.assertEqual(self.service.get_event("e1").status, "changes requested")
        self.assertEqual(self.db.query(EventReview).filter(EventReview.action == "approve").count(), 0)
        self.mocks["notify"].assert_not_called()

    def test_once_confirmed_the_request_is_approved(self):
        self.event(status="changes requested")
        self.clarification()

        approved = self.approve(confirm=True)

        self.assertEqual(approved.status, "planning")
        self.assertEqual(self.db.query(EventStatusHistory).one().fromStatus, "changes requested")


class TestUnassigned(ApprovalCase):
    """AC5."""

    def test_a_submitted_request_with_no_coordinator_cannot_be_approved(self):
        self.event(status="submitted", coordinatorId=None)

        error = self.refused()

        self.assertEqual(error.status_code, 409)
        self.assertIn("no coordinator", error.detail)
        self.assertEqual(self.service.get_event("e1").status, "submitted")
        self.mocks["notify"].assert_not_called()


class TestArrangementsStayOutstanding(ApprovalCase):
    """AC6: approval books nothing, so venue and equipment stay outstanding."""

    def test_approval_makes_no_venue_or_equipment_call(self):
        self.event()
        with patch("app.services.event_service.affected_arrangements") as affected, patch(
            "app.services.event_service.flag_arrangements"
        ) as flag, patch("app.orchestration.clients.httpx.Client", side_effect=AssertionError("no outbound call")):
            approved = self.approve()

        self.assertEqual(approved.status, "planning")
        affected.assert_not_called()
        flag.assert_not_called()


class TestApprovalRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.list_users", return_value=DIRECTORY),
            patch("app.services.event_service.send_notification", return_value=True),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", return_value=COORDINATOR)
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_approve_with_a_note_then_read_the_decision(self):
        insert_event(self.db, eventId="e1", status="under review", coordinatorId=COORDINATOR["userId"])

        approved = self.client.post("/events/e1/approve", headers=HEADERS, json={"note": "Ready for planning"})

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(
            (approved.json()["status"], approved.json()["decisionNote"], approved.json()["decidedBy"]),
            ("planning", "Ready for planning", "coord-1"),
        )
        self.assertTrue(approved.json()["decidedAt"])
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})

        decision = self.client.get("/events/e1/decision", headers=HEADERS)
        self.assertEqual(decision.status_code, 200)
        self.assertEqual((decision.json()["decision"], decision.json()["decisionNote"]), ("approved", "Ready for planning"))

    def test_open_clarifications_are_a_409_until_confirmed(self):
        insert_event(self.db, eventId="e1", status="changes requested", coordinatorId=COORDINATOR["userId"])
        self.db.add(
            EventReview(reviewId="rv-1", eventId="e1", reviewerId="coord-1", action="request_clarification", comment="?", status="open")
        )
        self.db.commit()

        warned = self.client.post("/events/e1/approve", headers=HEADERS, json={})
        self.assertEqual(warned.status_code, 409)
        self.assertTrue(warned.json()["detail"]["requiresConfirmation"])

        confirmed = self.client.post("/events/e1/approve", headers=HEADERS, json={"confirmOpenClarifications": True})
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual(confirmed.json()["status"], "planning")

    def test_a_note_over_2000_characters_is_refused(self):
        insert_event(self.db, eventId="e1", status="under review", coordinatorId=COORDINATOR["userId"])

        response = self.client.post("/events/e1/approve", headers=HEADERS, json={"note": "x" * 2001})

        self.assertEqual(response.status_code, 422)
