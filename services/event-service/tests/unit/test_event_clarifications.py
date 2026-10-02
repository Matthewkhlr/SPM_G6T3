from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event import Event
from app.models.event_clarification_reply import EventClarificationReply
from app.models.event_review import EventReview
from app.models.event_status_history import EventStatusHistory
from app.schemas.event import ClarificationCreate, ClarificationReplyCreate
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event

DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "coord-2", "userName": "Cara Ng", "email": "cara@connectsphere.com", "role": "coordinator"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
]
COORDINATOR = {"userId": "coord-1", "role": "coordinator"}
OTHER_COORDINATOR = {"userId": "coord-2", "role": "coordinator"}
ORGANISER = {"userId": "org-1", "role": "organiser", "organisationId": "o1"}
COLLEAGUE = {"userId": "org-2", "role": "organiser", "organisationId": "o1"}
OTHER_ORGANISATION = {"userId": "org-9", "role": "organiser", "organisationId": "o9"}
VENUE_STAFF = {"userId": "venue-1", "role": "venue"}
TECH_STAFF = {"userId": "tech-1", "role": "techsupport"}
ATTENDEE = {"userId": "att-1", "role": "attendee"}
QUESTION = "Please confirm expected attendance."
HEADERS = {"Authorization": "Bearer token"}


class ClarificationCase(EventCase):
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

    def raise_(self, message=QUESTION, field=None, coordinator_id="coord-1", event_id="e1"):
        return self.service.raise_clarification(
            event_id, ClarificationCreate(message=message, field=field), coordinator_id, "Bearer token"
        )

    def reply(self, clarification_id, caller=ORGANISER, message="Attendance stays at 80."):
        return self.service.reply_to_clarification(
            "e1", clarification_id, ClarificationReplyCreate(message=message), caller, "Bearer token"
        )

    def resolve(self, clarification_id, coordinator_id="coord-1"):
        return self.service.resolve_clarification("e1", clarification_id, coordinator_id, "Bearer token")

    def refused(self, action, *args, **kwargs) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            action(*args, **kwargs)
        return ctx.exception

    def status(self):
        return self.service.get_event("e1").status

    def set_status(self, status):
        self.db.query(Event).filter(Event.eventId == "e1").update({"status": status})
        self.db.commit()

    def last_email(self):
        to, subject, body, _authorization = self.mocks["notify"].call_args.args
        return to, subject, body


class TestRaising(ClarificationCase):
    """AC1."""

    def test_the_assigned_coordinator_states_what_is_unclear_and_names_the_field(self):
        self.event()

        raised = self.raise_(field="expectedAttendance")

        self.assertEqual(
            (raised.message, raised.field, raised.status, raised.raisedBy, raised.eventId),
            (QUESTION, "expectedAttendance", "open", "coord-1", "e1"),
        )
        [question] = raised.entries
        self.assertEqual(
            (question.entryId, question.authorName, question.authorRole, question.message),
            (raised.clarificationId, "Ben Lee", "coordinator", QUESTION),
        )

    def test_the_field_is_optional(self):
        self.event()

        self.assertIsNone(self.raise_().field)

    def test_the_message_is_required_and_the_field_must_belong_to_an_event_request(self):
        with self.assertRaises(ValidationError):
            ClarificationCreate(message="   ")
        with self.assertRaises(ValidationError):
            ClarificationCreate(message=QUESTION, field="internalNotes")
        self.assertEqual(ClarificationCreate(message=f"  {QUESTION} ").message, QUESTION)
        self.assertIsNone(ClarificationCreate(message=QUESTION, field="").field)
        with self.assertRaises(ValidationError):
            ClarificationReplyCreate(message="")

    def test_another_coordinator_cannot_raise_one(self):
        self.event()

        self.assertEqual(self.refused(self.raise_, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.db.query(EventReview).count(), 0)

    def test_a_request_with_no_coordinator_cannot_take_one(self):
        self.event(status="submitted", coordinatorId=None)

        error = self.refused(self.raise_)

        self.assertEqual(error.status_code, 409)
        self.assertIn("no coordinator", error.detail)

    def test_only_a_request_in_review_can_take_one(self):
        for index, status in enumerate(("planning", "confirmed", "rejected", "completed", "cancelled")):
            insert_event(self.db, eventId=f"e-{index}", status=status, coordinatorId="coord-1")
            with self.subTest(status=status):
                self.assertEqual(self.refused(self.raise_, event_id=f"e-{index}").status_code, 409)
        self.assertEqual(self.db.query(EventReview).count(), 0)

    def test_a_missing_event_is_404(self):
        self.assertEqual(self.refused(self.raise_).status_code, 404)


class TestRaisingRequestsChanges(ClarificationCase):
    """AC2."""

    def test_raising_moves_the_request_to_changes_requested(self):
        self.event()

        self.raise_()

        self.assertEqual(self.status(), "changes requested")
        self.assertTrue(self.service.get_event("e1").hasOpenClarifications)
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual(
            (history.fromStatus, history.toStatus, history.changedBy, history.note),
            ("under review", "changes requested", "coord-1", "Clarification requested"),
        )

    def test_the_organiser_is_emailed_the_question_and_the_field(self):
        self.event()

        self.raise_(field="expectedAttendance")

        to, subject, body = self.last_email()
        self.assertEqual((to, subject), ("amy@apex.com", "Your coordinator has a question about Summit"))
        self.assertIn(f"Summit (Expected attendance): {QUESTION}", body)

    def test_without_a_field_the_email_names_none(self):
        self.event()

        self.raise_()

        self.assertIn(f"about Summit: {QUESTION}", self.last_email()[2])

    def test_a_second_clarification_adds_no_status_change(self):
        self.event()
        self.raise_()

        self.raise_(message="And the layout?")

        self.assertEqual(self.db.query(EventStatusHistory).count(), 1)
        self.assertEqual(self.status(), "changes requested")

    def test_an_unreachable_directory_does_not_undo_the_clarification(self):
        self.mocks["users"].side_effect = service_unavailable("down")
        self.event()

        raised = self.raise_()

        self.assertEqual(self.status(), "changes requested")
        self.assertIsNone(raised.entries[0].authorName)
        self.mocks["notify"].assert_not_called()

    def test_an_organiser_missing_from_the_directory_is_not_emailed(self):
        self.mocks["users"].return_value = DIRECTORY[:2]
        self.event()

        self.raise_()

        self.mocks["notify"].assert_not_called()


class TestThread(ClarificationCase):
    """AC3."""

    def test_the_question_and_replies_are_one_thread_in_order_with_author_role_and_time(self):
        self.event()
        raised = self.raise_()

        self.reply(raised.clarificationId, ORGANISER, "Attendance stays at 80.")
        thread = self.reply(raised.clarificationId, COORDINATOR, "Thanks, noted.")

        self.assertEqual(
            [(entry.authorName, entry.authorRole, entry.message) for entry in thread.entries],
            [("Ben Lee", "coordinator", QUESTION), ("Amy", "organiser", "Attendance stays at 80."), ("Ben Lee", "coordinator", "Thanks, noted.")],
        )
        times = [entry.createdAt for entry in thread.entries]
        self.assertEqual(times, sorted(times))
        [listed] = self.service.list_clarifications("e1", ORGANISER, "Bearer token")
        self.assertEqual(listed.entries, thread.entries)

    def test_an_organiser_reply_is_emailed_to_the_coordinator_and_a_coordinator_reply_to_the_organiser(self):
        self.event()
        raised = self.raise_()

        self.reply(raised.clarificationId, ORGANISER)
        self.assertEqual(self.last_email()[0], "ben@connectsphere.com")
        self.assertIn("Attendance stays at 80.", self.last_email()[2])

        self.reply(raised.clarificationId, COORDINATOR, "Thanks")
        self.assertEqual(self.last_email()[0], "amy@apex.com")

    def test_a_colleague_in_the_organisation_can_reply(self):
        self.event()
        raised = self.raise_()

        thread = self.reply(raised.clarificationId, COLLEAGUE)

        self.assertEqual((thread.entries[-1].authorId, thread.entries[-1].authorRole), ("org-2", "organiser"))

    def test_only_the_organisation_and_the_assigned_coordinator_can_reply(self):
        self.event()
        raised = self.raise_()

        for caller in (OTHER_ORGANISATION, OTHER_COORDINATOR, VENUE_STAFF):
            with self.subTest(caller=caller["userId"]):
                self.assertEqual(self.refused(self.reply, raised.clarificationId, caller).status_code, 403)
        self.assertEqual(self.db.query(EventClarificationReply).count(), 0)

    def test_a_resolved_clarification_takes_no_more_replies(self):
        self.event()
        raised = self.raise_()
        self.resolve(raised.clarificationId)

        self.assertEqual(self.refused(self.reply, raised.clarificationId).status_code, 409)

    def test_an_unknown_clarification_or_one_on_another_event_is_404(self):
        self.event()
        insert_event(self.db, eventId="e2", status="under review", coordinatorId="coord-1")
        other = self.raise_(event_id="e2")

        self.assertEqual(self.refused(self.reply, "missing").status_code, 404)
        self.assertEqual(self.refused(self.reply, other.clarificationId).status_code, 404)
        self.assertEqual(self.refused(self.resolve, other.clarificationId).status_code, 404)

    def test_a_late_reply_still_reaches_the_coordinator_flagged_as_late(self):
        self.event()
        raised = self.raise_()
        self.set_status("planning")

        self.reply(raised.clarificationId, ORGANISER)

        self.assertIn("no longer awaiting review; it is now planning", self.last_email()[2])

    def test_a_reply_with_no_coordinator_to_tell_is_still_saved(self):
        self.event(coordinatorId=None)
        self.db.add(EventReview(reviewId="rv-1", eventId="e1", reviewerId="coord-1", action="request_clarification", comment=QUESTION, status="open"))
        self.db.commit()

        thread = self.reply("rv-1", ORGANISER)

        self.assertEqual(len(thread.entries), 2)
        self.mocks["notify"].assert_not_called()


class TestTrackedIndependently(ClarificationCase):
    """AC4."""

    def test_several_clarifications_stay_open_or_resolved_on_their_own(self):
        self.event()
        first = self.raise_(message="First gap")
        second = self.raise_(message="Second gap")

        self.resolve(first.clarificationId)

        listed = self.service.list_clarifications("e1", COORDINATOR, "Bearer token")
        self.assertEqual([(row.message, row.status) for row in listed], [("First gap", "resolved"), ("Second gap", "open")])
        self.assertNotEqual(first.clarificationId, second.clarificationId)
        self.assertEqual(self.status(), "changes requested")


class TestResolving(ClarificationCase):
    """AC5."""

    def test_resolving_the_last_open_clarification_returns_the_request_to_under_review(self):
        self.event()
        first = self.raise_(message="First gap")
        second = self.raise_(message="Second gap")
        self.resolve(first.clarificationId)

        resolved = self.resolve(second.clarificationId)

        self.assertEqual((resolved.status, resolved.resolvedBy), ("resolved", "coord-1"))
        self.assertIsNotNone(resolved.resolvedAt)
        self.assertEqual(self.status(), "under review")
        self.assertFalse(self.service.get_event("e1").hasOpenClarifications)
        latest = self.service.get_activity_log("e1")[-1]
        self.assertEqual((latest.fromStatus, latest.toStatus, latest.note), ("changes requested", "under review", "All clarifications resolved"))

    def test_an_event_that_has_moved_on_keeps_its_status(self):
        self.event()
        raised = self.raise_()
        self.set_status("planning")

        self.resolve(raised.clarificationId)

        self.assertEqual(self.status(), "planning")

    def test_only_the_assigned_coordinator_resolves_and_only_once(self):
        self.event()
        raised = self.raise_()

        self.assertEqual(self.refused(self.resolve, raised.clarificationId, "coord-2").status_code, 403)
        self.resolve(raised.clarificationId)
        self.assertEqual(self.refused(self.resolve, raised.clarificationId).status_code, 409)


class TestVisibility(ClarificationCase):
    """AC6 and AC7."""

    def test_the_organisation_and_staff_see_threads_but_other_organisations_and_attendees_do_not(self):
        self.event()
        self.raise_()

        for caller in (ORGANISER, COLLEAGUE, COORDINATOR, OTHER_COORDINATOR, VENUE_STAFF, TECH_STAFF):
            with self.subTest(caller=caller["userId"]):
                self.assertEqual(len(self.service.list_clarifications("e1", caller)), 1)
        for caller in (OTHER_ORGANISATION, ATTENDEE):
            with self.subTest(caller=caller["userId"]):
                self.assertEqual(self.refused(self.service.list_clarifications, "e1", caller).status_code, 403)

    def test_the_question_and_replies_stay_off_reads_attendees_can_make(self):
        self.event()
        raised = self.raise_()
        self.reply(raised.clarificationId, ORGANISER, "Secret answer")

        readable = str(self.service.get_event("e1")) + str(self.service.get_activity_log("e1"))

        self.assertNotIn(QUESTION, readable)
        self.assertNotIn("Secret answer", readable)

    def test_threads_stay_readable_after_the_event_is_confirmed_completed_or_cancelled(self):
        self.event()
        raised = self.raise_()
        self.reply(raised.clarificationId, ORGANISER)

        for status in ("confirmed", "completed", "cancelled"):
            self.set_status(status)
            with self.subTest(status=status):
                [thread] = self.service.list_clarifications("e1", ORGANISER)
                self.assertEqual(len(thread.entries), 2)

    def test_a_missing_event_is_404(self):
        self.assertEqual(self.refused(self.service.list_clarifications, "missing", ORGANISER).status_code, 404)


class TestDrafts(ClarificationCase):
    """AC8."""

    def test_a_draft_or_discarded_event_cannot_take_a_clarification(self):
        for status in ("draft", "discarded"):
            self.db.query(Event).delete()
            self.db.commit()
            self.event(status=status, coordinatorId="coord-1")
            with self.subTest(status=status):
                error = self.refused(self.raise_)
                self.assertEqual(error.status_code, 409)
                self.assertIn("not a request yet", error.detail)
                self.assertEqual(self.status(), status)
        self.assertEqual(self.db.query(EventReview).count(), 0)


class TestClarificationRoutes(ServiceTestCase):
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
        insert_event(self.db, eventId="e1", status="under review", coordinatorId="coord-1")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def as_caller(self, caller):
        self.caller_mock.return_value = caller

    def test_raise_reply_list_and_resolve(self):
        raised = self.client.post(
            "/events/e1/clarifications", headers=HEADERS, json={"message": QUESTION, "field": "expectedAttendance"}
        )
        self.assertEqual(raised.status_code, 201)
        self.assertEqual((raised.json()["status"], raised.json()["field"]), ("open", "expectedAttendance"))
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})
        clarification_id = raised.json()["clarificationId"]
        self.assertEqual(self.client.get("/events/e1", headers=HEADERS).json()["status"], "changes requested")

        self.as_caller(ORGANISER)
        replied = self.client.post(
            f"/events/e1/clarifications/{clarification_id}/reply", headers=HEADERS, json={"message": "80 people"}
        )
        self.assertEqual(replied.status_code, 201)
        self.assertEqual([entry["authorRole"] for entry in replied.json()["entries"]], ["coordinator", "organiser"])
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"organiser", "coordinator"})

        listed = self.client.get("/events/e1/clarifications", headers=HEADERS)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()[0]["entries"]), 2)

        self.as_caller(COORDINATOR)
        resolved = self.client.post(f"/events/e1/clarifications/{clarification_id}/resolve", headers=HEADERS)
        self.assertEqual(resolved.status_code, 200)
        self.assertEqual(resolved.json()["status"], "resolved")
        self.assertEqual(self.client.get("/events/e1", headers=HEADERS).json()["status"], "under review")

    def test_attendees_get_403(self):
        self.as_caller(ATTENDEE)

        self.assertEqual(self.client.get("/events/e1/clarifications", headers=HEADERS).status_code, 403)

    def test_a_blank_message_or_unknown_field_is_422(self):
        for body in ({"message": "  "}, {"message": QUESTION, "field": "notAField"}, {"field": "capacity"}):
            with self.subTest(body=body):
                self.assertEqual(self.client.post("/events/e1/clarifications", headers=HEADERS, json=body).status_code, 422)
