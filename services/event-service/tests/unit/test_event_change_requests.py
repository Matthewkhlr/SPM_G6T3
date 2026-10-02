from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event_change_request import EventChangeRequest
from app.models.event_field_change import EventFieldChange
from app.schemas.event import ChangeRequestAccept, ChangeRequestCreate, ChangeRequestDecline
from app.services.event_service import CHANGE_REQUEST_STATUSES, EventService
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event

START = datetime(2026, 12, 1, 9)
END = datetime(2026, 12, 1, 17)
DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
    {"userId": "org-2", "userName": "Dan", "email": "dan@apex.com", "role": "organiser", "organisationId": "o1"},
]
ORGANISER = {"userId": "org-1", "role": "organiser", "organisationId": "o1"}
COLLEAGUE = {"userId": "org-2", "role": "organiser", "organisationId": "o1"}
OTHER_ORGANISATION = {"userId": "org-9", "role": "organiser", "organisationId": "o9"}
COORDINATOR = {"userId": "coord-1", "role": "coordinator"}
ATTENDEE = {"userId": "att-1", "role": "attendee"}
VENUE = {"kind": "venue", "id": "vb-1", "summary": "Venue booking at Marina Hall A"}
HEADERS = {"Authorization": "Bearer token"}


class ChangeRequestCase(EventCase):
    def setUp(self):
        super().setUp()
        self.patches = {
            "names": patch("app.services.event_service.organisation_names", return_value={}),
            "users": patch("app.services.event_service.list_users", return_value=DIRECTORY),
            "email": patch("app.services.event_service.send_notification", return_value=True),
            "inbox": patch("app.services.event_service.record_notification", return_value=True),
            "affected": patch("app.services.event_service.affected_arrangements", return_value=[]),
            "flag": patch("app.services.event_service.flag_arrangements", return_value=[]),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        super().tearDown()

    def event(self, event_id="e1", status="planning", coordinatorId="coord-1", **overrides):
        values = dict(
            eventName="Summit", description="Original", layoutPreference="Theatre", expectedAttendance=50,
            proposedStartAt=START, proposedEndAt=END,
        )
        values.update(overrides)
        return insert_event(self.db, eventId=event_id, status=status, coordinatorId=coordinatorId, **values)

    def raise_(self, caller=ORGANISER, reason="Client asked", event_id="e1", **changes):
        return self.service.raise_change_request(
            event_id, ChangeRequestCreate(reason=reason, proposedChanges=changes or {"description": "Updated"}), caller, "Bearer token"
        )

    def accept(self, change_request_id, reason="", confirm=False, coordinator_id="coord-1"):
        return self.service.accept_change_request(
            "e1", change_request_id, ChangeRequestAccept(reason=reason, confirmSignificantChange=confirm), coordinator_id, "Bearer token"
        )

    def decline(self, change_request_id, reason="Keep the original copy", coordinator_id="coord-1"):
        return self.service.decline_change_request(
            "e1", change_request_id, ChangeRequestDecline(reason=reason), coordinator_id, "Bearer token"
        )

    def withdraw(self, change_request_id, caller=ORGANISER):
        return self.service.withdraw_change_request("e1", change_request_id, caller, "Bearer token")

    def refused(self, action, *args, **kwargs) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            action(*args, **kwargs)
        return ctx.exception

    def stored(self, event_id="e1"):
        return self.service.get_event(event_id)

    def last_email(self):
        to, subject, body, _ = self.mocks["email"].call_args.args
        return to, subject, body

    def legacy_request(self, proposed):
        self.db.add(
            EventChangeRequest(
                changeRequestId="cr-old", eventId="e1", requestedBy="org-1", status="pending", summary="Old date change",
                proposedChanges=proposed, affectsVenue=False, affectsEquipment=False, affectsRegistration=False,
                createdAt=datetime.utcnow(),
            )
        )
        self.db.commit()


class TestRaising(ChangeRequestCase):
    """AC1."""

    def test_the_organiser_can_ask_at_every_stage_from_review_to_confirmed(self):
        for index, status in enumerate(CHANGE_REQUEST_STATUSES):
            self.event(event_id=f"e-{index}", status=status)
            with self.subTest(status=status):
                self.assertEqual(self.raise_(event_id=f"e-{index}").status, "pending")

    def test_a_colleague_in_the_organisation_can_ask(self):
        self.event()

        self.assertEqual(self.raise_(caller=COLLEAGUE).requestedBy, "org-2")

    def test_another_organisation_or_a_coordinator_cannot(self):
        self.event()

        for caller in (OTHER_ORGANISATION, COORDINATOR):
            with self.subTest(caller=caller["userId"]):
                self.assertEqual(self.refused(self.raise_, caller=caller).status_code, 403)

    def test_a_submitted_request_has_no_coordinator_to_ask_yet(self):
        self.event(status="submitted", coordinatorId=None)

        self.assertEqual(self.refused(self.raise_).status_code, 409)

    def test_a_missing_event_is_404(self):
        self.assertEqual(self.refused(self.raise_).status_code, 404)


class TestCurrentProposedAndReason(ChangeRequestCase):
    """AC2."""

    def test_each_field_is_stored_with_its_current_and_proposed_value_and_the_reason(self):
        self.event()

        raised = self.raise_(reason="Client restated the purpose", description="New copy", expectedAttendance=80)

        self.assertEqual(raised.reason, "Client restated the purpose")
        self.assertEqual(raised.proposedChanges, {"description": "New copy", "expectedAttendance": 80})
        self.assertEqual(raised.currentValues, {"description": "Original", "expectedAttendance": 50})
        self.assertEqual(raised.requestedBy, "org-1")

    def test_a_reason_is_required(self):
        for reason in ("", "   "):
            with self.subTest(reason=reason), self.assertRaises(ValidationError):
                ChangeRequestCreate(reason=reason, proposedChanges={"description": "x"})
        with self.assertRaises(ValidationError):
            ChangeRequestCreate(proposedChanges={"description": "x"})

    def test_unchanged_values_are_left_out_and_nothing_to_change_is_refused(self):
        self.event()

        raised = self.raise_(description="Original", eventName="Summit 2027")
        self.assertEqual(raised.proposedChanges, {"eventName": "Summit 2027"})
        self.withdraw(raised.changeRequestId)

        error = self.refused(self.raise_, description="Original")
        self.assertEqual((error.status_code, error.detail), (422, "The proposed values are the same as the event's current details"))

    def test_the_end_must_stay_after_the_start(self):
        self.event()

        self.assertEqual(self.refused(self.raise_, proposedEndAt=START - timedelta(hours=1)).status_code, 422)
        self.assertEqual(self.refused(self.raise_, proposedStartAt=END + timedelta(hours=1)).status_code, 422)
        moved = self.raise_(proposedStartAt=START + timedelta(days=7), proposedEndAt=END + timedelta(days=7))
        self.assertEqual(moved.proposedChanges["proposedStartAt"], "2026-12-08T09:00:00")
        self.assertEqual(moved.currentValues["proposedStartAt"], "2026-12-01T09:00:00")


class TestChangeableFields(ChangeRequestCase):
    """AC3."""

    def test_the_published_fields(self):
        self.assertEqual(
            EventService.changeable_fields().fields,
            [
                "eventName", "description", "purpose", "category", "proposedStartAt", "proposedEndAt",
                "expectedAttendance", "layoutPreference", "accessibilityNeeds", "equipmentRequirements",
            ],
        )

    def test_other_fields_and_invalid_values_are_refused(self):
        for proposed in ({"internalNotes": "x"}, {"capacity": 5}, {}, {"expectedAttendance": -1}, {"eventName": None}):
            with self.subTest(proposed=proposed), self.assertRaises(ValidationError):
                ChangeRequestCreate(reason="r", proposedChanges=proposed)

    def test_times_are_stored_in_utc(self):
        aware = datetime(2026, 12, 1, 17, tzinfo=timezone(timedelta(hours=8)))

        created = ChangeRequestCreate(reason="r", proposedChanges={"proposedStartAt": aware})

        self.assertEqual(created.proposedChanges, {"proposedStartAt": "2026-12-01T09:00:00"})


class TestPendingAndNotified(ChangeRequestCase):
    """AC4."""

    def test_the_assigned_coordinator_is_emailed_the_fields_and_reason(self):
        self.event()

        self.raise_(reason="Need banquet", layoutPreference="Banquet", expectedAttendance=90)

        to, subject, body = self.last_email()
        self.assertEqual((to, subject), ("ben@connectsphere.com", "Change requested for Summit"))
        self.assertIn("Amy has asked to change expected attendance, layout on Summit. Reason: Need banquet", body)

    def test_both_sides_see_it_pending_with_the_proposed_values_and_attendees_do_not(self):
        self.event()
        self.raise_(layoutPreference="Banquet")

        for caller in (ORGANISER, COLLEAGUE, COORDINATOR):
            with self.subTest(caller=caller["userId"]):
                [listed] = self.service.list_change_requests("e1", caller)
                self.assertEqual((listed.status, listed.proposedChanges), ("pending", {"layoutPreference": "Banquet"}))
        for caller in (OTHER_ORGANISATION, ATTENDEE):
            with self.subTest(caller=caller["userId"]):
                self.assertEqual(self.refused(self.service.list_change_requests, "e1", caller).status_code, 403)

    def test_requests_are_listed_newest_first(self):
        self.event()
        first = self.raise_(description="A")
        self.withdraw(first.changeRequestId)
        self.db.query(EventChangeRequest).update({"createdAt": datetime.utcnow() - timedelta(days=1)})
        self.db.commit()

        second = self.raise_(description="B")

        listed = self.service.list_change_requests("e1", ORGANISER)
        self.assertEqual([row.changeRequestId for row in listed], [second.changeRequestId, first.changeRequestId])

    def test_it_names_what_the_change_could_unsettle(self):
        self.event()
        cases = [
            ({"description": "x"}, (False, False, False)),
            ({"layoutPreference": "Banquet"}, (True, False, False)),
            ({"equipmentRequirements": "Mics"}, (False, True, False)),
            ({"proposedStartAt": START + timedelta(hours=1)}, (True, True, True)),
        ]
        for proposed, expected in cases:
            with self.subTest(proposed=proposed):
                raised = self.raise_(**proposed)
                self.assertEqual((raised.affectsVenue, raised.affectsEquipment, raised.affectsRegistration), expected)
                self.withdraw(raised.changeRequestId)

    def test_an_unreachable_directory_or_no_coordinator_still_raises_it(self):
        self.mocks["users"].side_effect = service_unavailable("down")
        self.event()
        self.event(event_id="e2", status="approved", coordinatorId=None)

        self.assertEqual(self.raise_().status, "pending")
        self.assertEqual(self.raise_(event_id="e2").status, "pending")
        self.mocks["email"].assert_not_called()


class TestOnePending(ChangeRequestCase):
    """AC5."""

    def test_a_second_request_waits_until_the_first_is_withdrawn(self):
        self.event()
        first = self.raise_(description="A")

        error = self.refused(self.raise_, description="B")
        self.assertEqual(error.status_code, 409)
        self.assertIn("Withdraw it before requesting another", error.detail)

        self.withdraw(first.changeRequestId)
        self.assertEqual(self.raise_(description="B").status, "pending")


class TestWithdrawing(ChangeRequestCase):
    """AC6."""

    def test_the_organiser_withdraws_their_own_request_and_the_coordinator_is_told(self):
        self.event()
        raised = self.raise_(description="temp")

        withdrawn = self.withdraw(raised.changeRequestId)

        self.assertEqual((withdrawn.status, withdrawn.reviewedBy), ("withdrawn", "org-1"))
        self.assertIsNotNone(withdrawn.reviewedAt)
        to, subject, body = self.last_email()
        self.assertEqual((to, subject), ("ben@connectsphere.com", "Change request withdrawn for Summit"))
        self.assertIn("Amy has withdrawn their request to change description", body)

    def test_only_the_organiser_who_asked_and_only_while_pending(self):
        self.event()
        raised = self.raise_()

        self.assertEqual(self.refused(self.withdraw, raised.changeRequestId, COLLEAGUE).status_code, 403)
        self.withdraw(raised.changeRequestId)
        self.assertEqual(self.refused(self.withdraw, raised.changeRequestId).status_code, 409)
        self.assertEqual(self.refused(self.withdraw, "missing").status_code, 404)

    def test_with_no_coordinator_to_tell_it_still_withdraws(self):
        self.event(status="approved", coordinatorId=None)
        raised = self.raise_()

        self.assertEqual(self.withdraw(raised.changeRequestId).status, "withdrawn")
        self.mocks["email"].assert_not_called()


class TestDecision(ChangeRequestCase):
    """AC7."""

    def test_a_declined_request_leaves_the_event_and_tells_the_organiser_why(self):
        self.event()
        raised = self.raise_(description="x")

        declined = self.decline(raised.changeRequestId, "Keep the original copy")

        self.assertEqual((declined.status, declined.decisionReason, declined.reviewedBy), ("declined", "Keep the original copy", "coord-1"))
        self.assertEqual(self.stored().description, "Original")
        to, subject, body = self.last_email()
        self.assertEqual((to, subject), ("amy@apex.com", "Your change request for Summit was declined"))
        self.assertIn("Reason: Keep the original copy", body)
        user_id, event_id, kind, title, in_app, _ = self.mocks["inbox"].call_args.args
        self.assertEqual((user_id, event_id, kind, title, in_app), ("org-1", "e1", "event.change_request", subject, body))

    def test_declining_needs_a_reason(self):
        with self.assertRaises(ValidationError):
            ChangeRequestDecline(reason="  ")

    def test_an_accepted_request_is_applied_logged_and_the_organiser_told(self):
        self.event()
        raised = self.raise_(description="New copy", eventName="Summit 2027")

        accepted = self.accept(raised.changeRequestId, reason="Agreed with the venue")

        self.assertEqual((accepted.status, accepted.decisionReason), ("accepted", "Agreed with the venue"))
        stored = self.stored()
        self.assertEqual((stored.description, stored.eventName), ("New copy", "Summit 2027"))
        logged = {row.field: (row.oldValue, row.newValue, row.changedBy) for row in self.db.query(EventFieldChange)}
        self.assertEqual(logged["description"], ("Original", "New copy", "coord-1"))
        body = self.last_email()[2]
        self.assertIn("was accepted", self.last_email()[1])
        self.assertIn("Reason: Agreed with the venue The event now shows the new details.", body)

    def test_accepting_without_a_reason_says_none(self):
        self.event()
        raised = self.raise_()

        self.assertIsNone(self.accept(raised.changeRequestId, reason="  ").decisionReason)
        self.assertNotIn("Reason:", self.last_email()[2])

    def test_a_significant_change_to_a_confirmed_event_needs_confirming_like_an_edit(self):
        self.mocks["affected"].return_value = [VENUE]
        self.mocks["flag"].return_value = [VENUE]
        self.event(status="confirmed")
        raised = self.raise_(expectedAttendance=200)

        error = self.refused(self.accept, raised.changeRequestId)
        self.assertEqual(error.status_code, 409)
        self.assertTrue(error.detail["requiresConfirmation"])
        self.assertEqual(self.service.list_change_requests("e1", COORDINATOR)[0].status, "pending")
        self.assertEqual(self.stored().expectedAttendance, 50)

        accepted = self.accept(raised.changeRequestId, confirm=True)
        self.assertEqual([row.id for row in accepted.flaggedArrangements], ["vb-1"])
        self.assertEqual((self.stored().status, self.stored().expectedAttendance), ("reconsidering", 200))

    def test_only_the_assigned_coordinator_decides_and_only_once(self):
        self.event()
        raised = self.raise_()

        self.assertEqual(self.refused(self.accept, raised.changeRequestId, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.refused(self.decline, raised.changeRequestId, coordinator_id="coord-2").status_code, 403)
        self.decline(raised.changeRequestId)
        self.assertEqual(self.refused(self.accept, raised.changeRequestId).status_code, 409)
        self.assertEqual(self.refused(self.decline, raised.changeRequestId).status_code, 409)
        self.assertEqual(self.refused(self.accept, "missing").status_code, 404)

    def test_a_request_whose_values_cannot_be_applied_is_refused_unchanged(self):
        self.event()
        self.legacy_request({"proposedStartAt": "shifted earlier"})

        error = self.refused(self.accept, "cr-old")

        self.assertEqual(error.status_code, 422)
        self.assertEqual(self.service.list_change_requests("e1", COORDINATOR)[0].status, "pending")
        self.assertEqual(self.decline("cr-old").status, "declined")

    def test_an_organiser_missing_from_the_directory_still_gets_the_in_app_notice(self):
        self.event()
        raised = self.raise_()
        self.mocks["email"].reset_mock()
        self.mocks["users"].return_value = DIRECTORY[:1]

        self.decline(raised.changeRequestId)

        self.mocks["email"].assert_not_called()
        self.assertEqual(self.mocks["inbox"].call_args.args[0], "org-1")


class TestNotOffered(ChangeRequestCase):
    """AC8 and AC9."""

    def test_a_draft_is_edited_directly(self):
        for index, status in enumerate(("draft", "discarded")):
            self.event(event_id=f"e-{index}", status=status, coordinatorId=None)
            with self.subTest(status=status):
                error = self.refused(self.raise_, event_id=f"e-{index}")
                self.assertEqual((error.status_code, error.detail), (409, "A draft is edited directly, so there is no change to request"))

    def test_a_finished_event_takes_no_change_request(self):
        for index, status in enumerate(("completed", "cancelled", "rejected")):
            self.event(event_id=f"e-{index}", status=status)
            with self.subTest(status=status):
                self.assertEqual(self.refused(self.raise_, event_id=f"e-{index}").status_code, 409)
        self.assertEqual(self.db.query(EventChangeRequest).count(), 0)


class TestConfirmedStaysConfirmed(ChangeRequestCase):
    """AC10."""

    def test_a_pending_request_changes_nothing_on_the_event(self):
        self.event(status="confirmed")
        before = self.stored()

        self.raise_(proposedStartAt=START + timedelta(days=7), proposedEndAt=END + timedelta(days=7), layoutPreference="Banquet")

        after = self.stored()
        self.assertEqual(after.status, "confirmed")
        self.assertEqual(after.model_dump(), before.model_dump())
        self.assertEqual(self.db.query(EventFieldChange).count(), 0)
        self.mocks["affected"].assert_not_called()


class TestChangeRequestRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.list_users", return_value=DIRECTORY),
            patch("app.services.event_service.send_notification", return_value=True),
            patch("app.services.event_service.record_notification", return_value=True),
            patch("app.services.event_service.affected_arrangements", return_value=[]),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", return_value=ORGANISER)
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        insert_event(self.db, eventId="e1", status="planning", coordinatorId="coord-1", description="Original")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def post(self, path, body=None):
        return self.client.post(f"/events/e1/change-requests{path}", headers=HEADERS, json=body)

    def test_raise_list_withdraw_decline_and_accept(self):
        fields = self.client.get("/events/changeable-fields", headers=HEADERS)
        self.assertEqual(fields.status_code, 200)
        self.assertIn("layoutPreference", fields.json()["fields"])

        self.assertEqual(self.post("", {"proposedChanges": {"description": "x"}}).status_code, 422)
        raised = self.post("", {"reason": "Tweak", "proposedChanges": {"description": "x"}})
        self.assertEqual(raised.status_code, 201)
        self.assertEqual(raised.json()["currentValues"], {"description": "Original"})
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"organiser"})
        self.assertEqual(self.post("", {"reason": "Again", "proposedChanges": {"description": "y"}}).status_code, 409)
        listed = self.client.get("/events/e1/change-requests", headers=HEADERS)
        self.assertEqual([row["status"] for row in listed.json()], ["pending"])

        withdrawn = self.post(f"/{raised.json()['changeRequestId']}/withdraw")
        self.assertEqual((withdrawn.status_code, withdrawn.json()["status"]), (200, "withdrawn"))

        second = self.post("", {"reason": "Second", "proposedChanges": {"description": "y"}}).json()["changeRequestId"]
        self.caller_mock.return_value = COORDINATOR
        declined = self.post(f"/{second}/decline", {"reason": "Keep the original copy"})
        self.assertEqual((declined.status_code, declined.json()["decisionReason"]), (200, "Keep the original copy"))
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})

        self.caller_mock.return_value = ORGANISER
        third = self.post("", {"reason": "Third", "proposedChanges": {"description": "z"}}).json()["changeRequestId"]
        self.caller_mock.return_value = COORDINATOR
        accepted = self.post(f"/{third}/accept", {})
        self.assertEqual((accepted.status_code, accepted.json()["status"]), (200, "accepted"))
        self.assertEqual(self.client.get("/events/e1", headers=HEADERS).json()["description"], "z")
