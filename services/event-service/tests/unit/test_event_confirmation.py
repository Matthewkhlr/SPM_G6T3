from datetime import datetime, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event import Event
from app.models.event_field_change import EventFieldChange
from app.models.event_safety_review import EventSafetyReview
from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EquipmentNotRequired
from app.services.arrangements import covers, equipment_gaps, venue_gaps
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event

START = datetime(2026, 12, 1, 9)
END = datetime(2026, 12, 1, 17)
DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
    {"userId": "venue-1", "userName": "Vinod", "email": "vinod@connectsphere.com", "role": "venue"},
    {"userId": "tech-1", "userName": "Tia", "email": "tia@connectsphere.com", "role": "techsupport"},
]
BOOKING = {
    "bookingId": "vb-1",
    "venueId": "v1",
    "venueName": "Marina Hall A",
    "startsAt": "2026-12-01T08:30:00",
    "endsAt": "2026-12-01T17:30:00",
    "status": "approved",
    "reviewedBy": "venue-1",
}
REQUEST = {
    "requestId": "rq-1",
    "eventId": "e1",
    "equipmentId": "eq1",
    "quantity": 2,
    "status": "reserved",
    "reviewNote": "",
    "reviewedBy": "tech-1",
}
RESERVATION = {"reservationId": "rs-1", "requestId": "rq-1", "equipmentId": "eq1", "quantity": 2, "status": "active"}
NAMES = {"eq1": "Projector", "eq2": "Microphone"}
HEADERS = {"Authorization": "Bearer token"}


class TestVenueRule(ServiceTestCase):
    def test_no_booking_at_all_is_missing(self):
        self.assertEqual([gap["message"] for gap in venue_gaps([], START, END)], ["No venue has been booked for this event yet."])
        withdrawn = {**BOOKING, "status": "withdrawn"}
        self.assertEqual(len(venue_gaps([withdrawn], START, END)), 1)

    def test_every_requested_venue_must_be_approved(self):
        pending = {**BOOKING, "bookingId": "vb-2", "venueName": None, "venueId": "v2", "status": "pending"}

        [gap] = venue_gaps([BOOKING, pending], START, END)

        self.assertEqual(gap, {"kind": "venue", "message": "Venue staff have not approved the booking at v2 yet."})

    def test_an_approved_booking_must_be_for_the_events_date_and_time(self):
        self.assertEqual(venue_gaps([BOOKING], START, END), [])
        earlier = {**BOOKING, "startsAt": "2026-11-20T09:00:00Z", "endsAt": "2026-11-20T17:00:00Z"}

        [gap] = venue_gaps([earlier], START, END)

        self.assertIn("(20 Nov 2026 09:00 to 20 Nov 2026 17:00) is not for the event's date and time", gap["message"])
        self.assertFalse(covers(BOOKING, None, END))
        self.assertTrue(covers({**BOOKING, "startsAt": START, "endsAt": END}, START, END))

    def test_times_with_and_without_an_offset_compare_in_utc(self):
        offset = {**BOOKING, "startsAt": START.isoformat() + "+08:00", "endsAt": END.isoformat() + "+08:00"}
        self.assertFalse(covers(offset, START, END))

        aware = START.replace(tzinfo=timezone.utc)
        self.assertTrue(covers({**BOOKING, "startsAt": START.isoformat() + "+00:00"}, aware, END))


class TestEquipmentRule(ServiceTestCase):
    def test_a_request_not_yet_reserved_is_missing(self):
        [gap] = equipment_gaps([], [{**REQUEST, "status": "approved"}], [], NAMES)

        self.assertEqual(
            gap, {"kind": "equipment", "message": "2 × Projector is approved but technical support have not reserved it yet."}
        )
        self.assertEqual(equipment_gaps([], [REQUEST, {**REQUEST, "status": "complete"}], [], NAMES), [])

    def test_each_unsettled_request_says_what_it_waits_on(self):
        messages = [
            equipment_gaps([], [{**REQUEST, "status": status}], [], NAMES)[0]["message"]
            for status in ("partial", "unavailable", "attention")
        ]

        self.assertEqual(
            messages,
            [
                "2 × Projector is only partly reserved. Accept the shortfall or wait for technical support.",
                "2 × Projector is unavailable. Accept the shortfall or wait for technical support.",
                "2 × Projector needs technical support's attention.",
            ],
        )

    def test_a_shortfall_the_coordinator_accepted_settles_the_line(self):
        line = {"equipmentId": "eq1", "quantity": 3}
        accepted = {**REQUEST, "status": "resolved"}

        self.assertEqual(equipment_gaps([line], [accepted], [{**RESERVATION, "quantity": 1}], NAMES), [])

    def test_an_equipment_line_must_be_reserved_or_recorded_as_not_required(self):
        line = {"equipmentId": "eq2", "quantity": 1}

        [gap] = equipment_gaps([line], [], [], NAMES)
        self.assertEqual((gap["equipmentId"], gap["message"]), ("eq2", "1 × Microphone is neither reserved nor recorded as not required."))

        self.assertEqual(equipment_gaps([{**line, "notRequired": True}], [], [], NAMES), [])
        held = {**RESERVATION, "equipmentId": "eq2", "quantity": 1}
        self.assertEqual(equipment_gaps([line], [], [held, {**held, "status": "released"}], NAMES), [])
        self.assertEqual(equipment_gaps([line], [{**REQUEST, "equipmentId": "eq2", "status": "complete"}], [], NAMES), [])

    def test_a_line_short_of_its_quantity_is_missing_and_a_pending_request_is_named_once(self):
        line = {"equipmentId": "eq1", "quantity": 3}
        self.assertEqual(len(equipment_gaps([line], [REQUEST], [RESERVATION], NAMES)), 1)

        gaps = equipment_gaps([line], [{**REQUEST, "status": "pending"}], [], {})
        self.assertEqual([gap["message"] for gap in gaps], ["2 × eq1 is waiting for technical support to review it."])


class ConfirmationCase(EventCase):
    def setUp(self):
        super().setUp()
        self.patches = {
            "names": patch("app.services.event_service.organisation_names", return_value={}),
            "users": patch("app.services.event_service.list_users", return_value=DIRECTORY),
            "email": patch("app.services.event_service.send_notification", return_value=True),
            "inbox": patch("app.services.event_service.record_notification", return_value=True),
            "bookings": patch("app.services.event_service.event_bookings", return_value=[BOOKING]),
            "requests": patch("app.services.event_service.equipment_requests_for", return_value=[REQUEST]),
            "reservations": patch("app.services.event_service.equipment_reservations_for", return_value=[RESERVATION]),
            "equipment": patch("app.services.event_service.equipment_names", return_value=NAMES),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        super().tearDown()

    def event(self, event_id="e1", status="safety approved", coordinatorId="coord-1", **overrides):
        values = dict(eventName="Summit", proposedStartAt=START, proposedEndAt=END, layoutPreference="Theatre")
        values.update(overrides)
        return insert_event(self.db, eventId=event_id, status=status, coordinatorId=coordinatorId, **values)

    def review(self, status, note=None, event_id="e1"):
        self.db.add(
            EventSafetyReview(
                reviewId=f"sr-{status}", eventId=event_id, status=status, submittedBy="coord-1",
                submittedAt=datetime.utcnow(), crowdMovement="x", equipmentPlacement="", package={}, decisionNote=note,
            )
        )
        self.db.commit()

    def gaps(self, event_id="e1", coordinator_id="coord-1"):
        return self.service.confirmation(event_id, coordinator_id, "Bearer token")

    def refused(self, action, *args, **kwargs) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            action(*args, **kwargs)
        return ctx.exception

    def confirm(self, event_id="e1", coordinator_id="coord-1"):
        return self.service.confirm_event(event_id, coordinator_id, "Bearer token")


class TestWhatIsMissing(ConfirmationCase):
    """AC1 and AC2, with the safety review in front (SPM-120)."""

    def test_a_safety_approved_event_with_everything_arranged_is_ready(self):
        self.event()

        status = self.gaps()

        self.assertEqual((status.eventId, status.ready, status.missing), ("e1", True, []))

    def test_each_outstanding_arrangement_is_named(self):
        self.event(equipmentLines=[{"equipmentId": "eq2", "quantity": 1}])
        self.mocks["bookings"].return_value = [{**BOOKING, "status": "pending"}]

        status = self.gaps()

        self.assertFalse(status.ready)
        self.assertEqual([gap.kind for gap in status.missing], ["venue", "equipment"])
        self.assertEqual(status.missing[1].equipmentId, "eq2")

    def test_the_safety_review_must_have_passed(self):
        cases = [
            ("planning", None, None, "has not been sent for a safety review yet"),
            ("safety review", None, None, "has not reviewed it yet"),
            ("planning", "rejected", "Exits blocked.", "was rejected: Exits blocked. Revise"),
            ("planning", "changes_requested", "Widen aisles.", "asked for changes: Widen aisles. Submit"),
            ("planning", "superseded", "Start moved", "needs a new safety review"),
        ]
        for index, (event_status, review_status, note, expected) in enumerate(cases):
            event_id = f"e-{index}"
            self.event(event_id=event_id, status=event_status)
            if review_status:
                self.review(review_status, note, event_id=event_id)
            with self.subTest(review=review_status or event_status):
                [gap] = self.gaps(event_id).missing
                self.assertEqual(gap.kind, "safety")
                self.assertIn(expected, gap.message)

    def test_an_event_outside_planning_is_named_by_its_stage(self):
        self.event(event_id="e-sub", status="submitted")
        self.event(event_id="e-done", status="confirmed")

        self.assertIn("This one is submitted", self.gaps("e-sub").missing[0].message)
        self.assertEqual(self.gaps("e-done").missing[0].message, "This event is already confirmed.")
        self.mocks["bookings"].assert_not_called()

    def test_only_the_assigned_coordinator(self):
        self.event()
        self.event(event_id="e2", coordinatorId=None)

        self.assertEqual(self.refused(self.gaps, coordinator_id="coord-2").status_code, 403)
        self.assertEqual(self.refused(self.gaps, event_id="e2").status_code, 409)

    def test_unreachable_arrangements_are_a_503(self):
        self.event()
        self.mocks["bookings"].side_effect = service_unavailable("down")

        self.assertEqual(self.refused(self.gaps).status_code, 503)


class TestConfirming(ConfirmationCase):
    """AC3, AC4, AC5, and AC6."""

    def test_confirming_moves_the_event_to_confirmed_and_records_who_and_when(self):
        self.event()

        confirmed = self.confirm()

        self.assertEqual((confirmed.status, confirmed.decidedBy, confirmed.confirmedBy), ("confirmed", "coord-1", "coord-1"))
        self.assertEqual(confirmed.decidedAt, confirmed.confirmedAt)
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual((history.fromStatus, history.toStatus, history.changedBy), ("safety approved", "confirmed", "coord-1"))
        self.assertEqual(self.service.get_event("e1").confirmedBy, "coord-1")

    def test_the_organiser_and_the_staff_on_the_arrangements_are_notified(self):
        self.event(registrationEnabled=True, registrationOpensAt=datetime(2026, 11, 1, 9))

        self.confirm()

        emails = {call.args[0]: call.args[2] for call in self.mocks["email"].call_args_list}
        self.assertEqual(set(emails), {"amy@apex.com", "vinod@connectsphere.com", "tia@connectsphere.com"})
        organiser = emails["amy@apex.com"]
        self.assertIn("Summit is confirmed for 01 Dec 2026, 09:00 at Marina Hall A. Layout: Theatre. Equipment: 2 × Projector.", organiser)
        self.assertIn("Registration opens 01 Nov 2026, 09:00.", organiser)
        self.assertIn("which you arranged for, is confirmed", emails["vinod@connectsphere.com"])
        inboxes = {call.args[0]: call.args[2] for call in self.mocks["inbox"].call_args_list}
        self.assertEqual(inboxes, {"org-1": "event.confirmed", "venue-1": "event.confirmed", "tech-1": "event.confirmed"})

    def test_the_equipment_named_is_what_was_requested_and_any_line_still_needed(self):
        self.event(
            equipmentLines=[
                {"equipmentId": "eq1", "quantity": 2},
                {"equipmentId": "eq2", "quantity": 1},
                {"equipmentId": "eq3", "quantity": 4, "notRequired": True, "notRequiredReason": "Venue has its own."},
            ]
        )
        self.mocks["reservations"].return_value = [RESERVATION, {**RESERVATION, "equipmentId": "eq2", "quantity": 1}]

        self.confirm()

        organiser = next(call.args[2] for call in self.mocks["email"].call_args_list if call.args[0] == "amy@apex.com")
        self.assertIn("Equipment: 2 × Projector, 1 × Microphone.", organiser)

    def test_without_registration_or_equipment_the_message_says_so(self):
        self.event(layoutPreference=None)
        self.mocks["requests"].return_value = []
        self.mocks["reservations"].return_value = []

        self.confirm()

        organiser = next(call.args[2] for call in self.mocks["email"].call_args_list if call.args[0] == "amy@apex.com")
        self.assertIn("Layout: not set. Equipment: none.", organiser)
        self.assertNotIn("Registration opens", organiser)

    def test_an_unreachable_directory_does_not_undo_it(self):
        self.event()
        self.mocks["users"].side_effect = service_unavailable("down")

        self.assertEqual(self.confirm().status, "confirmed")
        self.mocks["email"].assert_not_called()
        self.assertEqual({call.args[0] for call in self.mocks["inbox"].call_args_list}, {"org-1", "venue-1", "tech-1"})

    def test_anything_missing_is_a_409_naming_it_and_saves_nothing(self):
        self.event(status="safety review")
        self.mocks["bookings"].return_value = [{**BOOKING, "status": "pending"}]

        error = self.refused(self.confirm)

        self.assertEqual(error.status_code, 409)
        self.assertEqual(error.detail["missing"], ["venue", "safety"])
        self.assertEqual(len(error.detail["gaps"]), 2)
        self.assertEqual(self.service.get_event("e1").status, "safety review")
        self.mocks["email"].assert_not_called()

    def test_an_arrangement_lost_after_the_safety_review_is_caught_now(self):
        self.event()
        self.mocks["bookings"].return_value = [{**BOOKING, "status": "cancelled"}]

        error = self.refused(self.confirm)

        self.assertEqual(error.detail["missing"], ["venue"])

    def test_a_confirmed_event_is_listed_for_attendees(self):
        self.event()
        self.confirm()

        self.assertEqual([row.eventId for row in self.service.list_confirmed_events()], ["e1"])


class TestNotRequired(ConfirmationCase):
    """AC1: an equipment line explicitly recorded as not required."""

    def line_event(self, status="planning"):
        return self.event(status=status, equipmentLines=[{"equipmentId": "eq2", "quantity": 1, "technicalNotes": ""}])

    def mark(self, reason="The venue has its own mics", coordinator_id="coord-1", equipment_id="eq2"):
        return self.service.mark_equipment_not_required(
            "e1", equipment_id, EquipmentNotRequired(reason=reason), coordinator_id, "Bearer token"
        )

    def test_marking_a_line_records_who_when_and_why_and_clears_the_gap(self):
        self.line_event()
        self.assertEqual(self.gaps().missing[0].equipmentId, "eq2")

        updated = self.mark()

        [line] = updated.equipmentLines
        self.assertEqual((line["notRequired"], line["notRequiredReason"], line["notRequiredBy"]), (True, "The venue has its own mics", "coord-1"))
        self.assertTrue(line["notRequiredAt"])
        self.assertNotIn("equipment", [gap.kind for gap in self.gaps().missing])
        change = self.db.query(EventFieldChange).one()
        self.assertEqual((change.field, change.oldValue, change.newValue), ("equipmentLine:eq2", "required", "not required: The venue has its own mics"))

    def test_it_can_be_undone_and_repeating_a_state_logs_nothing(self):
        self.line_event()
        self.mark()
        self.mark()
        self.assertEqual(self.db.query(EventFieldChange).count(), 1)

        restored = self.service.mark_equipment_required("e1", "eq2", "coord-1", "Bearer token")

        self.assertNotIn("notRequired", restored.equipmentLines[0])
        self.assertEqual(self.db.query(EventFieldChange).count(), 2)

    def test_only_the_assigned_coordinator_only_in_planning_and_only_existing_lines(self):
        self.line_event(status="safety approved")
        self.assertEqual(self.refused(self.mark).status_code, 409)
        self.assertEqual(self.refused(self.mark, coordinator_id="coord-2").status_code, 403)
        self.db.query(Event).update({"status": "planning"})
        self.db.commit()
        self.assertEqual(self.refused(self.mark, equipment_id="eq9").status_code, 404)

    def test_a_reason_is_required(self):
        with self.assertRaises(ValidationError):
            EquipmentNotRequired(reason="  ")


class TestConfirmationRoutes(ServiceTestCase):
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
            patch("app.services.event_service.equipment_requests_for", return_value=[]),
            patch("app.services.event_service.equipment_reservations_for", return_value=[]),
            patch("app.services.event_service.equipment_names", return_value=NAMES),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch(
            "app.routers.event.resolve_caller", return_value={"userId": "coord-1", "role": "coordinator"}
        )
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

    def test_check_mark_not_required_and_confirm(self):
        insert_event(
            self.db, eventId="e1", status="planning", coordinatorId="coord-1", proposedStartAt=START, proposedEndAt=END,
            equipmentLines=[{"equipmentId": "eq2", "quantity": 1}],
        )
        status = self.client.get("/events/e1/confirmation", headers=HEADERS).json()
        self.assertEqual([gap["kind"] for gap in status["missing"]], ["equipment", "safety"])
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})

        marked = self.client.post("/events/e1/equipment-lines/eq2/not-required", headers=HEADERS, json={"reason": "Not needed"})
        self.assertEqual((marked.status_code, marked.json()["equipmentLines"][0]["notRequired"]), (200, True))
        restored = self.client.delete("/events/e1/equipment-lines/eq2/not-required", headers=HEADERS)
        self.assertNotIn("notRequired", restored.json()["equipmentLines"][0])
        self.client.post("/events/e1/equipment-lines/eq2/not-required", headers=HEADERS, json={"reason": "Not needed"})

        refused = self.client.post("/events/e1/confirm", headers=HEADERS)
        self.assertEqual((refused.status_code, refused.json()["detail"]["missing"]), (409, ["safety"]))

        self.db.query(Event).update({"status": "safety approved"})
        self.db.commit()
        confirmed = self.client.post("/events/e1/confirm", headers=HEADERS)
        self.assertEqual(confirmed.status_code, 200)
        self.assertEqual((confirmed.json()["status"], confirmed.json()["decidedBy"]), ("confirmed", "coord-1"))
        self.assertTrue(confirmed.json()["decidedAt"])
