"""SPM-120, change 6: Venue Staff and technical support send their confirmed
arrangements to the Safety Officer, and the review opens once every part the
event needs is in."""

from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event_safety_handoff import EventSafetyHandoff
from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EventUpdate, SafetySubmission, SafetyTechnicalHandoff, SafetyVenueHandoff
from app.services.arrangements import technical_needed
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import insert_event
from tests.unit.test_event_safety_reviews import (
    BOOKING,
    COORDINATOR,
    DIRECTORY,
    END,
    HEADERS,
    ORGANISER,
    RESERVATION,
    REQUEST,
    START,
    VENUE,
    SafetyCase,
    resolve_as,
)

CROWD = SafetyVenueHandoff(crowdMovement="Enter by the lobby, leave by the promenade.")
PLACEMENT = SafetyTechnicalHandoff(equipmentPlacement="Projector on the lectern, cables taped down.")
VENUE_STAFF = {"userId": "venue-1", "role": "venue"}
TECH = {"userId": "tech-1", "role": "techsupport"}
ATTENDEE = {"userId": "att-1", "role": "attendee"}


class HandoffCase(SafetyCase):
    def send_venue(self, data=CROWD):
        return self.service.send_venue_arrangements("e1", data, "venue-1", "Bearer token")

    def send_technical(self, data=PLACEMENT):
        return self.service.send_technical_arrangements("e1", data, "tech-1", "Bearer token")

    def stored(self):
        return self.db.get(EventSafetyHandoff, "e1")

    def safety_gap(self):
        missing = self.service.confirmation("e1", "coord-1", "Bearer token").missing
        return next(gap.message for gap in missing if gap.kind == "safety")


class TestTechnicalNeeded(ServiceTestCase):
    def test_any_equipment_on_the_event_needs_the_technical_arrangements(self):
        self.assertFalse(technical_needed([], [], []))
        self.assertTrue(technical_needed([], [REQUEST], []))
        self.assertTrue(technical_needed([], [], [RESERVATION]))
        self.assertFalse(technical_needed([], [], [{**RESERVATION, "status": "released"}]))
        self.assertTrue(technical_needed([{"equipmentId": "eq1", "quantity": 1}], [], []))
        self.assertFalse(technical_needed([{"equipmentId": "eq1", "quantity": 1, "notRequired": True}], [], []))


class TestVenueStaffSend(HandoffCase):
    def test_without_equipment_the_venue_arrangements_open_the_review(self):
        self.event()

        sent = self.send_venue()

        self.assertEqual((sent.venue.sentBy, sent.technical, sent.technicalNeeded), ("venue-1", None, False))
        self.assertEqual((sent.review.status, sent.review.submittedBy), ("pending", "venue-1"))
        self.assertEqual(sent.review.package.crowdMovement, CROWD.crowdMovement)
        self.assertEqual(self.status(), "safety review")
        self.assertIsNone(self.stored())
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual((history.changedBy, history.note), ("venue-1", "Arrangements sent for safety review"))
        told = {args[0] for args in self.inboxes()}
        self.assertEqual(told, {"safety-1", "safety-2", "coord-1"})
        coordinator = next(args for args in self.emails() if args[0] == "ben@connectsphere.com")
        self.assertEqual(coordinator[1], "Summit is with the Safety Officer")

    def test_with_equipment_it_waits_for_technical_support_then_opens(self):
        self.event()
        self.with_equipment()

        waiting = self.send_venue()

        self.assertIsNone(waiting.review)
        self.assertEqual((waiting.venue.note, waiting.technical, waiting.technicalNeeded), (CROWD.crowdMovement, None, True))
        self.assertEqual(self.status(), "planning")
        self.assertIn("Waiting on technical support", self.safety_gap())

        opened = self.send_technical()

        self.assertEqual((opened.review.submittedBy, opened.technical.sentBy), ("tech-1", "tech-1"))
        self.assertEqual(opened.review.package.equipmentPlacement, PLACEMENT.equipmentPlacement)
        self.assertEqual(opened.review.package.crowdMovement, CROWD.crowdMovement)
        self.assertEqual(self.status(), "safety review")

    def test_a_venue_not_yet_approved_is_refused_and_nothing_is_saved(self):
        self.event()
        self.mocks["bookings"].return_value = [{**BOOKING, "status": "pending"}]

        error = self.refused(self.send_venue)

        self.assertEqual((error.status_code, error.detail["missing"]), (409, ["venue"]))
        self.assertIsNone(self.stored())

    def test_only_from_planning(self):
        self.event(status="safety review")

        error = self.refused(self.send_venue)

        self.assertEqual(error.status_code, 409)
        self.assertIn("from planning", error.detail)

    def test_sending_again_replaces_the_note(self):
        self.event()
        self.with_equipment()
        self.send_venue()

        again = self.send_venue(SafetyVenueHandoff(crowdMovement="One way through the north doors."))

        self.assertEqual(again.venue.note, "One way through the north doors.")


class TestTechnicalSupportSend(HandoffCase):
    def test_an_event_without_equipment_has_nothing_technical_to_send(self):
        self.event()

        error = self.refused(self.send_technical)

        self.assertEqual(error.status_code, 409)
        self.assertIn("no equipment", error.detail)

    def test_equipment_not_yet_reserved_is_refused(self):
        self.event()
        self.mocks["requests"].return_value = [{**REQUEST, "status": "approved"}]

        error = self.refused(self.send_technical)

        self.assertEqual((error.status_code, error.detail["missing"]), (409, ["equipment"]))

    def test_technical_first_then_the_venue_opens_it(self):
        self.event()
        self.with_equipment()

        waiting = self.send_technical()

        self.assertEqual((waiting.review, waiting.venue), (None, None))
        self.assertIn("Waiting on Venue Staff", self.safety_gap())
        self.assertEqual(self.send_venue().review.submittedBy, "venue-1")

    def test_a_part_whose_arrangements_changed_since_is_cleared(self):
        self.event()
        self.with_equipment()
        self.send_technical()
        self.mocks["requests"].return_value = [{**REQUEST, "status": "approved"}]

        sent = self.send_venue()

        self.assertEqual((sent.review, sent.technical), (None, None))
        self.assertIn("Waiting on technical support", self.safety_gap())

        self.mocks["requests"].return_value = [REQUEST]
        self.mocks["bookings"].return_value = [{**BOOKING, "status": "pending"}]
        sent = self.send_technical()

        self.assertEqual((sent.review, sent.venue), (None, None))
        self.assertEqual(sent.technical.sentBy, "tech-1")


class TestCoordinatorAndChanges(HandoffCase):
    def test_the_coordinator_sending_everything_replaces_parts_already_sent(self):
        self.event()
        self.with_equipment()
        self.send_venue()

        review = self.submit(data=SafetySubmission(crowdMovement="Coordinator's plan.", equipmentPlacement="Stage left."))

        self.assertEqual((review.submittedBy, review.package.crowdMovement), ("coord-1", "Coordinator's plan."))
        self.assertIsNone(self.stored())

    def test_a_significant_change_clears_what_was_sent_and_a_quiet_one_keeps_it(self):
        self.event()
        self.with_equipment()
        self.send_venue()

        self.service.update_event("e1", EventUpdate(description="Typo fixed"), "coord-1")
        self.assertIsNotNone(self.stored())

        self.service.update_event("e1", EventUpdate(expectedAttendance=400, confirmSignificantChange=True), "coord-1")
        self.assertIsNone(self.stored())

    def test_the_organisation_and_staff_can_read_what_was_sent(self):
        self.event()
        self.with_equipment()
        self.send_venue()

        seen = self.service.safety_handoff("e1", ORGANISER, "Bearer token")

        self.assertEqual((seen.venue.sentBy, seen.technical, seen.technicalNeeded), ("venue-1", None, True))
        self.assertEqual(self.refused(self.service.safety_handoff, "e1", ATTENDEE, "Bearer token").status_code, 403)

    def test_notes_cannot_be_blank(self):
        with self.assertRaises(ValidationError):
            SafetyVenueHandoff(crowdMovement="  ")
        with self.assertRaises(ValidationError):
            SafetyTechnicalHandoff(equipmentPlacement="  ")


class TestHandoffRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.list_users", return_value=DIRECTORY),
            patch("app.services.event_service.send_notification", return_value=True),
            patch("app.services.event_service.record_notification", return_value=True),
            patch("app.services.event_service.event_bookings", return_value=[BOOKING]),
            patch("app.services.event_service.venue_details", return_value=VENUE),
            patch("app.services.event_service.equipment_requests_for", return_value=[REQUEST]),
            patch("app.services.event_service.equipment_reservations_for", return_value=[RESERVATION]),
            patch("app.services.event_service.equipment_names", return_value={"eq1": "Projector"}),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch("app.routers.event.resolve_caller", side_effect=resolve_as(VENUE_STAFF))
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

    def test_venue_staff_then_technical_support_open_the_review(self):
        venue = self.client.post("/events/e1/safety-handoff/venue", headers=HEADERS, json={"crowdMovement": "One way."})
        self.assertEqual((venue.status_code, venue.json()["review"]), (200, None))

        self.as_caller(TECH)
        read = self.client.get("/events/e1/safety-handoff", headers=HEADERS)
        self.assertEqual(read.json()["venue"]["sentBy"], "venue-1")
        technical = self.client.post(
            "/events/e1/safety-handoff/technical", headers=HEADERS, json={"equipmentPlacement": "Stage left."}
        )
        self.assertEqual((technical.status_code, technical.json()["review"]["status"]), (200, "pending"))

    def test_each_part_is_only_for_its_own_staff(self):
        for caller in (COORDINATOR, ORGANISER, TECH):
            self.as_caller(caller)
            response = self.client.post("/events/e1/safety-handoff/venue", headers=HEADERS, json={"crowdMovement": "x"})
            self.assertEqual(response.status_code, 403, caller["role"])
        for caller in (COORDINATOR, ORGANISER, VENUE_STAFF):
            self.as_caller(caller)
            response = self.client.post(
                "/events/e1/safety-handoff/technical", headers=HEADERS, json={"equipmentPlacement": "x"}
            )
            self.assertEqual(response.status_code, 403, caller["role"])
