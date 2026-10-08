from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event_safety_review import EventSafetyReview
from app.models.event_status_history import EventStatusHistory
from app.orchestration import clients
from app.schemas.event import EventUpdate, SafetyApproval, SafetyChangeRequest, SafetyRejection, SafetySubmission
from app.services.arrangements import requested_lines, technical_confirmed
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden, service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event
from tests.unit.test_event_arrangement_clients import fake_client, reply

START = datetime(2026, 12, 1, 9)
END = datetime(2026, 12, 1, 17)
DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
    {"userId": "safety-1", "userName": "Hana Yusof", "email": "hana@connectsphere.com", "role": "safety"},
    {"userId": "safety-2", "userName": "Ravi Nair", "email": "ravi@connectsphere.com", "role": "safety"},
]
BOOKING = {
    "bookingId": "vb-1",
    "venueId": "v1",
    "startsAt": "2026-12-01T09:00:00",
    "endsAt": "2026-12-01T17:00:00",
    "status": "approved",
    "needsReverification": False,
    "reverificationNote": None,
}
VENUE = {
    "venueId": "v1",
    "name": "Marina Hall A",
    "location": "HarbourFront Centre",
    "capacity": 300,
    "layouts": [{"name": "Theatre", "capacity": 300}, {"name": "Banquet", "capacity": 220}],
    "accessibility": ["Wheelchair accessible"],
    "emergencyAccess": "Four exits; assembly point at the promenade.",
    "restrictions": "No open flames.",
    "operatingHours": [{"day": "Mon", "opens": "08:00", "closes": "22:00"}],
}
REQUEST = {
    "requestId": "rq-1",
    "eventId": "e1",
    "equipmentId": "eq1",
    "quantity": 2,
    "status": "reserved",
    "technicalRequirements": "HDMI at the lectern",
    "reviewNote": "",
}
RESERVATION = {"reservationId": "rs-1", "requestId": "rq-1", "eventId": "e1", "quantity": 2, "status": "active"}
COORDINATOR = {"userId": "coord-1", "role": "coordinator"}
ORGANISER = {"userId": "org-1", "role": "organiser", "organisationId": "o1"}
OFFICER = {"userId": "safety-1", "role": "safety"}
SUBMISSION = SafetySubmission(crowdMovement="Enter by the lobby, leave by the promenade.", equipmentPlacement="")
HEADERS = {"Authorization": "Bearer token"}


class SafetyCase(EventCase):
    def setUp(self):
        super().setUp()
        self.patches = {
            "names": patch("app.services.event_service.organisation_names", return_value={}),
            "users": patch("app.services.event_service.list_users", return_value=DIRECTORY),
            "email": patch("app.services.event_service.send_notification", return_value=True),
            "inbox": patch("app.services.event_service.record_notification", return_value=True),
            "bookings": patch("app.services.event_service.approved_bookings", return_value=[BOOKING]),
            "venue": patch("app.services.event_service.venue_details", return_value=VENUE),
            "requests": patch("app.services.event_service.equipment_requests_for", return_value=[]),
            "reservations": patch("app.services.event_service.equipment_reservations_for", return_value=[]),
            "equipment": patch("app.services.event_service.equipment_names", return_value={"eq1": "Projector"}),
            "flag_venue": patch(
                "app.services.event_service.flag_venue_arrangements",
                return_value=[{"kind": "venue", "id": "vb-1", "summary": "Venue booking at Marina Hall A"}],
            ),
            "flag_technical": patch(
                "app.services.event_service.flag_technical_arrangements",
                return_value=[{"kind": "equipment", "id": "rs-1", "summary": "Equipment reservation: 2 x Projector"}],
            ),
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
            eventName="Summit", proposedStartAt=START, proposedEndAt=END, expectedAttendance=250,
            layoutPreference="Theatre", accessibilityNeeds="Ramp",
        )
        values.update(overrides)
        return insert_event(self.db, eventId=event_id, status=status, coordinatorId=coordinatorId, **values)

    def with_equipment(self):
        self.mocks["requests"].return_value = [REQUEST]
        self.mocks["reservations"].return_value = [RESERVATION]

    def submit(self, coordinator_id="coord-1", event_id="e1", data=SUBMISSION):
        return self.service.submit_safety_review(event_id, data, coordinator_id, "Bearer token")

    def refused(self, action, *args, **kwargs) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            action(*args, **kwargs)
        return ctx.exception

    def status(self, event_id="e1"):
        return self.service.get_event(event_id).status

    def approve(self, review_id, note=""):
        return self.service.approve_safety_review("e1", review_id, SafetyApproval(note=note), "safety-1", "Bearer token")

    def reject(self, review_id, reason="Exits blocked by the stage."):
        return self.service.reject_safety_review("e1", review_id, SafetyRejection(reason=reason), "safety-1", "Bearer token")

    def request_changes(self, review_id, changes="Move the stage away from exit B.", affected=()):
        return self.service.request_safety_changes(
            "e1", review_id, SafetyChangeRequest(requiredChanges=changes, affected=list(affected)), "safety-1", "Bearer token"
        )

    def emails(self):
        return [call.args for call in self.mocks["email"].call_args_list]

    def inboxes(self):
        return [call.args for call in self.mocks["inbox"].call_args_list]


class TestAvailableOnlyWhenArranged(SafetyCase):
    """AC1."""

    def test_no_confirmed_venue_booking_is_refused_naming_it(self):
        self.event()
        self.mocks["bookings"].return_value = []

        error = self.refused(self.submit)

        self.assertEqual(error.status_code, 409)
        self.assertEqual(error.detail["missing"], ["venue"])
        self.assertIn("Venue staff have not confirmed", error.detail["message"])
        self.assertEqual(self.status(), "planning")
        self.assertEqual(self.db.query(EventSafetyReview).count(), 0)

    def test_equipment_not_yet_reserved_is_refused_naming_it(self):
        self.event()
        self.mocks["bookings"].return_value = []
        self.mocks["requests"].return_value = [{**REQUEST, "status": "approved"}]

        error = self.refused(self.submit)

        self.assertEqual(error.detail["missing"], ["venue", "technical"])
        self.assertIn("Technical support have not reserved", error.detail["message"])

    def test_once_both_are_confirmed_it_goes_to_safety_review_and_every_officer_is_told(self):
        self.event()
        self.with_equipment()

        review = self.submit(data=SafetySubmission(crowdMovement="One way round.", equipmentPlacement="Back wall"))

        self.assertEqual((review.status, review.submittedBy), ("pending", "coord-1"))
        self.assertEqual(self.status(), "safety review")
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual((history.fromStatus, history.toStatus, history.note), ("planning", "safety review", "Submitted for safety review"))
        self.assertEqual({args[0] for args in self.emails()}, {"hana@connectsphere.com", "ravi@connectsphere.com"})
        self.assertEqual({args[0] for args in self.inboxes()}, {"safety-1", "safety-2"})
        self.assertEqual(self.emails()[0][1], "Summit is ready for a safety review")

    def test_an_event_needing_no_equipment_has_nothing_technical_to_wait_for(self):
        self.event()

        self.assertEqual(self.submit().package.equipment, [])

    def test_equipment_placement_is_required_when_equipment_is_reserved(self):
        self.event()
        self.with_equipment()

        error = self.refused(self.submit)

        self.assertEqual((error.status_code, error.detail), (422, "Say where the reserved equipment will be placed."))

    def test_only_the_assigned_coordinator_and_only_from_planning(self):
        self.event()
        self.event(event_id="e2", coordinatorId=None)
        self.event(event_id="e3", status="confirmed")

        self.assertEqual(self.refused(self.submit, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.refused(self.submit, event_id="e2").status_code, 409)
        error = self.refused(self.submit, event_id="e3")
        self.assertEqual(error.status_code, 409)
        self.assertIn("from planning", error.detail)

    def test_a_flagged_booking_still_counts_and_the_officer_sees_the_flag(self):
        self.event()
        self.mocks["bookings"].return_value = [{**BOOKING, "needsReverification": True, "reverificationNote": "Start moved"}]

        venue = self.submit().package.venues[0]

        self.assertEqual((venue.needsReverification, venue.reverificationNote), (True, "Start moved"))

    def test_unreachable_arrangements_submit_nothing(self):
        self.event()
        self.mocks["bookings"].side_effect = service_unavailable("down")

        self.assertEqual(self.refused(self.submit).status_code, 503)
        self.assertEqual(self.status(), "planning")


class TestWhatTheOfficerSees(SafetyCase):
    """AC2."""

    def test_attendance_venue_capacity_and_layout_emergency_access_restrictions_and_accessibility(self):
        self.event(accessibilitySelections=["Wheelchair accessible", "Hearing loop"], accessibilityNote="Two wheelchair users")

        package = self.submit().package

        self.assertEqual((package.expectedAttendance, package.layout), (250, "Theatre"))
        venue = package.venues[0]
        self.assertEqual((venue.venueName, venue.layout, venue.capacityInLayout, venue.venueCapacity), ("Marina Hall A", "Theatre", 300, 300))
        self.assertEqual(venue.emergencyAccess, "Four exits; assembly point at the promenade.")
        self.assertEqual(venue.restrictions, "No open flames.")
        self.assertEqual(venue.accessibilityFeatures, ["Wheelchair accessible"])
        self.assertEqual(package.accessibilityRequirements, ["Wheelchair accessible", "Hearing loop"])
        self.assertEqual(package.accessibilityNote, "Two wheelchair users")
        self.assertEqual(package.crowdMovement, "Enter by the lobby, leave by the promenade.")

    def test_the_layout_is_matched_whatever_its_case_and_otherwise_the_largest_applies(self):
        self.event(layoutPreference="banquet")
        self.assertEqual(self.submit().package.venues[0].capacityInLayout, 220)

        self.event(event_id="e2", layoutPreference="Cabaret", accessibilityNeeds="")
        venue = self.submit(event_id="e2").package.venues[0]
        self.assertEqual((venue.layout, venue.capacityInLayout), (None, 300))

    def test_typed_accessibility_needs_are_shown_when_none_were_picked(self):
        self.event()

        self.assertEqual(self.submit().package.accessibilityRequirements, ["Ramp"])

    def test_equipment_lines_with_names_placement_and_flags(self):
        self.event()
        self.with_equipment()
        self.mocks["reservations"].return_value = [{**RESERVATION, "needsReverification": True}]

        package = self.submit(data=SafetySubmission(crowdMovement="x", equipmentPlacement=" Back wall ")).package

        [line] = package.equipment
        self.assertEqual((line.name, line.quantity, line.technicalRequirements, line.needsReverification), ("Projector", 2, "HDMI at the lectern", True))
        self.assertEqual(package.equipmentPlacement, "Back wall")

    def test_the_queue_lists_pending_reviews_longest_waiting_first(self):
        self.event()
        self.event(event_id="e2")
        first = self.submit()
        self.db.query(EventSafetyReview).update({"submittedAt": datetime.utcnow() - timedelta(days=1)})
        self.db.commit()
        second = self.submit(event_id="e2")

        self.assertEqual([row.reviewId for row in self.service.list_safety_reviews()], [first.reviewId, second.reviewId])
        self.assertEqual(self.service.list_safety_reviews("approved"), [])

    def test_the_organisation_and_staff_see_reviews_but_not_attendees_or_other_organisations(self):
        self.event()
        self.submit()

        for caller in (ORGANISER, COORDINATOR, OFFICER, {"userId": "v-1", "role": "venue"}):
            with self.subTest(role=caller["role"]):
                self.assertEqual(len(self.service.get_safety_reviews("e1", caller)), 1)
        for caller in ({"userId": "att-1", "role": "attendee"}, {"userId": "org-9", "role": "organiser", "organisationId": "o9"}):
            with self.subTest(role=caller["role"]), self.assertRaises(HTTPException) as ctx:
                self.service.get_safety_reviews("e1", caller)
            self.assertEqual(ctx.exception.status_code, 403)


class TestApproving(SafetyCase):
    """AC3 and AC4."""

    def test_approve_records_the_decision_the_officer_and_the_time_and_moves_on_to_preparation(self):
        self.event()
        review = self.submit()
        self.mocks["email"].reset_mock()
        self.mocks["inbox"].reset_mock()

        approved = self.approve(review.reviewId, note="Good plan")

        self.assertEqual((approved.status, approved.decidedBy, approved.decisionNote), ("approved", "safety-1", "Good plan"))
        self.assertIsNotNone(approved.decidedAt)
        self.assertEqual(self.status(), "preparing")
        self.assertEqual({args[0] for args in self.emails()}, {"ben@connectsphere.com", "amy@apex.com"})
        self.assertIn("so it moves on to preparation. Note: Good plan", self.emails()[0][2])
        self.assertEqual({args[0] for args in self.inboxes()}, {"coord-1", "org-1"})

    def test_the_note_is_optional(self):
        self.event()

        approved = self.approve(self.submit().reviewId, note="  ")

        self.assertIsNone(approved.decisionNote)
        self.assertNotIn("Note:", self.emails()[-1][2])


class TestRejecting(SafetyCase):
    """AC5 and AC9."""

    def test_reject_records_the_reason_and_the_event_returns_to_planning_not_cancelled(self):
        self.event()
        review = self.submit()

        rejected = self.reject(review.reviewId, "Exits blocked by the stage.")

        self.assertEqual((rejected.status, rejected.decisionNote), ("rejected", "Exits blocked by the stage."))
        self.assertEqual(self.status(), "planning")
        to, subject, body, _ = self.mocks["email"].call_args.args
        self.assertEqual(subject, "Summit did not pass its safety review")
        self.assertIn("Reason: Exits blocked by the stage. The event is not cancelled", body)
        self.mocks["flag_venue"].assert_not_called()

    def test_the_coordinator_can_revise_and_submit_again(self):
        self.event()
        first = self.submit()
        self.reject(first.reviewId)

        second = self.submit()

        history = self.service.get_safety_reviews("e1", COORDINATOR)
        self.assertEqual([(row.reviewId, row.status) for row in history], [(second.reviewId, "pending"), (first.reviewId, "rejected")])

    def test_a_reason_is_required(self):
        with self.assertRaises(ValidationError):
            SafetyRejection(reason="   ")


class TestRequestingChanges(SafetyCase):
    """AC6."""

    def test_what_must_change_is_recorded_and_the_named_arrangements_are_flagged_for_review(self):
        self.event()
        review = self.submit()

        changed = self.request_changes(review.reviewId, "Move the stage.", affected=("venue", "technical", "venue"))

        self.assertEqual((changed.status, changed.decisionNote, changed.affected), ("changes_requested", "Move the stage.", ["venue", "technical"]))
        self.assertEqual(self.status(), "planning")
        self.mocks["flag_venue"].assert_called_once_with("e1", "Safety review: Move the stage.", "Bearer token")
        self.mocks["flag_technical"].assert_called_once_with("e1", "Safety review: Move the stage.", "Bearer token")
        self.assertEqual([row.id for row in changed.flaggedArrangements], ["vb-1", "rs-1"])
        self.assertIn("Flagged for re-checking: venue, technical arrangements.", self.emails()[-1][2])

    def test_nothing_named_flags_nothing(self):
        self.event()

        changed = self.request_changes(self.submit().reviewId)

        self.assertEqual(changed.flaggedArrangements, [])
        self.mocks["flag_venue"].assert_not_called()
        self.assertNotIn("Flagged", self.emails()[-1][2])

    def test_a_flag_that_cannot_be_set_saves_nothing(self):
        self.event()
        review = self.submit()
        self.mocks["flag_venue"].side_effect = service_unavailable("down")

        self.assertEqual(self.refused(self.request_changes, review.reviewId, affected=("venue",)).status_code, 503)
        self.assertEqual(self.status(), "safety review")

    def test_inputs_are_checked(self):
        for body in ({"requiredChanges": " "}, {"requiredChanges": "x", "affected": ["catering"]}):
            with self.subTest(body=body), self.assertRaises(ValidationError):
                SafetyChangeRequest(**body)
        with self.assertRaises(ValidationError):
            SafetySubmission(crowdMovement="  ")


class TestDecisionRules(SafetyCase):
    def test_a_review_can_be_decided_only_once(self):
        self.event()
        review = self.submit()
        self.approve(review.reviewId)

        for action in (self.approve, self.reject, self.request_changes):
            with self.subTest(action=action.__name__):
                error = self.refused(action, review.reviewId)
                self.assertEqual((error.status_code, error.detail), (409, "This safety review is already approved"))

    def test_an_unknown_review_is_404(self):
        self.event()
        self.submit()

        self.assertEqual(self.refused(self.approve, "missing").status_code, 404)

    def test_an_unreachable_directory_does_not_undo_a_decision(self):
        self.event()
        review = self.submit()
        self.mocks["users"].side_effect = service_unavailable("down")

        self.assertEqual(self.reject(review.reviewId).status, "rejected")
        self.assertEqual({args[0] for args in self.inboxes()[-2:]}, {"coord-1", "org-1"})


class TestChangesDuringReview(SafetyCase):
    """A significant change while under review withdraws the review."""

    def test_a_significant_edit_needs_confirming_then_withdraws_the_review(self):
        self.event()
        review = self.submit()

        with self.assertRaises(HTTPException) as ctx:
            self.service.update_event("e1", EventUpdate(expectedAttendance=400), "coord-1")
        self.assertEqual(ctx.exception.detail["statusChange"], {"from": "safety review", "to": "planning"})
        self.assertIn("withdraws the pending safety review", ctx.exception.detail["message"])

        self.service.update_event("e1", EventUpdate(expectedAttendance=400, confirmSignificantChange=True), "coord-1")

        self.assertEqual(self.status(), "planning")
        [withdrawn] = self.service.get_safety_reviews("e1", COORDINATOR)
        self.assertEqual((withdrawn.reviewId, withdrawn.status, withdrawn.decidedBy), (review.reviewId, "superseded", "coord-1"))
        self.assertIn("Expected attendance: 250 -> 400", withdrawn.decisionNote)

    def test_a_quiet_edit_leaves_the_review_alone(self):
        self.event()
        self.submit()

        self.service.update_event("e1", EventUpdate(description="Typo fixed"), "coord-1")

        self.assertEqual(self.status(), "safety review")

    def test_a_status_left_without_its_review_still_returns_to_planning(self):
        self.event(status="safety review")

        self.service.update_event("e1", EventUpdate(expectedAttendance=400, confirmSignificantChange=True), "coord-1")

        self.assertEqual(self.status(), "planning")


class TestArrangementRules(ServiceTestCase):
    def test_requested_lines_leave_out_closed_and_bookkeeping_requests(self):
        rows = [
            {"status": "reserved"},
            {"status": "rejected"},
            {"status": "cancelled"},
            {"status": "approved", "reviewNote": "Reserved from the catalogue quantity check"},
        ]
        self.assertEqual(requested_lines(rows), [{"status": "reserved"}])

    def test_technical_confirmed(self):
        self.assertTrue(technical_confirmed([], []))
        self.assertTrue(technical_confirmed([], [{**RESERVATION, "status": "released"}]))
        self.assertTrue(technical_confirmed([REQUEST], [RESERVATION]))
        self.assertFalse(technical_confirmed([{**REQUEST, "status": "approved"}], []))
        self.assertFalse(technical_confirmed([], [{**RESERVATION, "status": "partial"}]))


class TestSafetyClients(ServiceTestCase):
    def test_bookings_venue_requests_reservations_and_names(self):
        stub, client = fake_client(
            reply(200, [BOOKING]),
            reply(200, VENUE),
            reply(200, [REQUEST, {**REQUEST, "eventId": "e2"}]),
            reply(200, [RESERVATION]),
            reply(200, [{"equipmentId": "eq1", "name": "Projector"}]),
        )
        with stub:
            self.assertEqual(clients.approved_bookings("e1", "Bearer token"), [BOOKING])
            self.assertEqual(clients.venue_details("v1", "Bearer token"), VENUE)
            self.assertEqual(clients.equipment_requests_for("e1", "Bearer token"), [REQUEST])
            self.assertEqual(clients.equipment_reservations_for("e1", "Bearer token"), [RESERVATION])
            self.assertEqual(clients.equipment_names("Bearer token"), {"eq1": "Projector"})
        calls = client.__enter__.return_value.request.call_args_list
        self.assertEqual(calls[0].kwargs["params"], {"eventId": "e1", "status": "approved"})
        self.assertTrue(calls[1].args[1].endswith("/venues/v1"))
        self.assertEqual(calls[3].kwargs["params"], {"eventId": "e1"})

    def test_an_unanswered_check_is_a_503_that_submits_nothing(self):
        stub, _client = fake_client(reply(500))
        with stub, self.assertRaises(HTTPException) as ctx:
            clients.approved_bookings("e1", None)
        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("nothing was submitted", ctx.exception.detail)

    def test_venue_and_technical_flags_can_be_set_separately(self):
        stub, client = fake_client(
            reply(200, [{**BOOKING, "venueName": "Marina Hall A"}]),
            reply(200, [{**RESERVATION, "equipmentId": "eq1", "equipmentName": "Projector"}]),
        )
        with stub:
            venue = clients.flag_venue_arrangements("e1", "Safety review: move it", None)
            technical = clients.flag_technical_arrangements("e1", "Safety review: move it", None)
        self.assertEqual((venue[0]["kind"], technical[0]["kind"]), ("venue", "equipment"))
        venue_call, technical_call = client.__enter__.return_value.request.call_args_list
        self.assertTrue(venue_call.args[1].endswith("/venues/bookings/reverification"))
        self.assertTrue(technical_call.args[1].endswith("/equipment/reservations/reverification"))


def resolve_as(caller):
    """A stand-in for resolve_caller that applies allowed_roles like the real one."""

    def resolve(authorization, user_service_url, allowed_roles=None, timeout=5.0):
        if allowed_roles is not None and caller["role"] not in allowed_roles:
            raise forbidden("You do not have permission to perform this action")
        return caller

    return resolve


class TestSafetyRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.list_users", return_value=DIRECTORY),
            patch("app.services.event_service.send_notification", return_value=True),
            patch("app.services.event_service.record_notification", return_value=True),
            patch("app.services.event_service.approved_bookings", return_value=[BOOKING]),
            patch("app.services.event_service.venue_details", return_value=VENUE),
            patch("app.services.event_service.equipment_requests_for", return_value=[]),
            patch("app.services.event_service.equipment_reservations_for", return_value=[]),
            patch("app.services.event_service.flag_venue_arrangements", return_value=[]),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", side_effect=resolve_as(COORDINATOR))
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        insert_event(self.db, eventId="e1", status="planning", coordinatorId="coord-1", proposedStartAt=START, proposedEndAt=END)

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def as_caller(self, caller):
        self.caller_mock.side_effect = resolve_as(caller)

    def submit(self):
        response = self.client.post("/events/e1/safety-reviews", headers=HEADERS, json={"crowdMovement": "One way."})
        self.assertEqual(response.status_code, 201)
        return response.json()["reviewId"]

    def decide(self, review_id, action, body):
        return self.client.post(f"/events/e1/safety-reviews/{review_id}/{action}", headers=HEADERS, json=body)

    def test_submit_queue_history_and_approve(self):
        review_id = self.submit()
        self.as_caller(OFFICER)
        queue = self.client.get("/events/safety-reviews", headers=HEADERS)
        self.assertEqual([row["reviewId"] for row in queue.json()], [review_id])
        self.assertEqual(queue.json()[0]["package"]["venues"][0]["emergencyAccess"], VENUE["emergencyAccess"])

        approved = self.decide(review_id, "approve", {})
        self.assertEqual((approved.status_code, approved.json()["status"]), (200, "approved"))
        self.assertEqual(self.client.get("/events/e1", headers=HEADERS).json()["status"], "preparing")
        history = self.client.get("/events/e1/safety-reviews", headers=HEADERS)
        self.assertEqual(history.json()[0]["decidedBy"], "safety-1")

    def test_reject_and_request_changes_through_the_api(self):
        review_id = self.submit()
        self.as_caller(OFFICER)
        self.assertEqual(self.decide(review_id, "reject", {}).status_code, 422)
        self.assertEqual(self.decide(review_id, "reject", {"reason": "Unsafe"}).json()["status"], "rejected")

        self.as_caller(COORDINATOR)
        second = self.submit()
        self.as_caller(OFFICER)
        changed = self.decide(second, "request-changes", {"requiredChanges": "Widen aisles", "affected": ["venue"]})
        self.assertEqual((changed.status_code, changed.json()["affected"]), (200, ["venue"]))

    def test_every_other_role_gets_403_on_every_decision(self):
        review_id = self.submit()
        others = [
            COORDINATOR,
            ORGANISER,
            {"userId": "v-1", "role": "venue"},
            {"userId": "t-1", "role": "techsupport"},
            {"userId": "att-1", "role": "attendee"},
        ]
        bodies = {"approve": {}, "reject": {"reason": "No"}, "request-changes": {"requiredChanges": "Change it"}}
        for caller in others:
            self.as_caller(caller)
            for action, body in bodies.items():
                with self.subTest(role=caller["role"], action=action):
                    self.assertEqual(self.decide(review_id, action, body).status_code, 403)
            with self.subTest(role=caller["role"], action="queue"):
                self.assertEqual(self.client.get("/events/safety-reviews", headers=HEADERS).status_code, 403)
        self.assertEqual(self.client.get("/events/e1", headers=HEADERS).json()["status"], "safety review")
