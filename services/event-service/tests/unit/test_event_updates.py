from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

from app.models.event_field_change import EventFieldChange
from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EventUpdate
from app.services.event_service import QUIET_FIELDS, SIGNIFICANT_FIELDS
from shared.exceptions.http import service_unavailable
from tests.unit.support import EventCase, insert_event

START = datetime(2026, 12, 1, 9)
END = datetime(2026, 12, 1, 17)
VENUE = {"kind": "venue", "id": "vb-1", "summary": "Venue booking at Marina Hall A, 01 Dec 2026 09:00 to 01 Dec 2026 17:00 UTC"}
EQUIPMENT = {"kind": "equipment", "id": "er-1", "summary": "Equipment reservation: 2 x Projector"}


class UpdateCase(EventCase):
    def setUp(self):
        super().setUp()
        self.names = patch("app.services.event_service.organisation_names", return_value={})
        self.affected = patch("app.services.event_service.affected_arrangements", return_value=[])
        self.flag = patch("app.services.event_service.flag_arrangements", return_value=[])
        self.names.start()
        self.affected_mock = self.affected.start()
        self.flag_mock = self.flag.start()

    def tearDown(self):
        self.flag.stop()
        self.affected.stop()
        self.names.stop()
        super().tearDown()

    def event(self, status="planning", **overrides):
        data = dict(
            eventId="e1",
            coordinatorId="coord-1",
            status=status,
            description="Old description",
            purpose="Old purpose",
            proposedStartAt=START,
            proposedEndAt=END,
            expectedAttendance=120,
            accessibilityNeeds="",
            equipmentRequirements="",
            venueRequirements="",
        )
        data.update(overrides)
        return insert_event(self.db, **data)

    def edits(self):
        return self.db.query(EventFieldChange).order_by(EventFieldChange.field).all()

    def update(self, event_id="e1", caller="coord-1", **body):
        return self.service.update_event(event_id, EventUpdate(**body), caller, "Bearer token")


class TestQuietEdits(UpdateCase):
    def test_quiet_fields_save_without_a_warning_or_an_arrangement_check(self):
        self.event(status="confirmed")

        updated = self.update(
            eventName="Partner Networking Night",
            description="New description",
            purpose="New purpose",
            category="networking",
            internalNotes="Staff only",
            organiserContact="organiser@connectsphere.com",
        )

        self.assertEqual(updated.eventName, "Partner Networking Night")
        self.assertEqual(updated.category, "networking")
        self.assertEqual(updated.internalNotes, "Staff only")
        self.assertEqual(updated.organiserContact, "organiser@connectsphere.com")
        self.assertEqual(updated.status, "confirmed")
        self.assertEqual(updated.flaggedArrangements, [])
        self.affected_mock.assert_not_called()
        self.flag_mock.assert_not_called()

    def test_every_quiet_edit_is_logged_with_the_field_old_and_new_value_actor_and_time(self):
        self.event()

        self.update(description="New description", category="networking")

        edits = self.edits()
        self.assertEqual([edit.field for edit in edits], ["category", "description"])
        self.assertEqual((edits[0].oldValue, edits[0].newValue), (None, "networking"))
        self.assertEqual((edits[1].oldValue, edits[1].newValue), ("Old description", "New description"))
        self.assertTrue(all(edit.changedBy == "coord-1" for edit in edits))
        self.assertTrue(all(edit.createdAt for edit in edits))

    def test_an_unchanged_value_is_not_an_edit(self):
        self.event(organiserContact=None)

        unchanged = self.update(description="Old description", organiserContact="", expectedAttendance=120)

        self.assertEqual(unchanged.description, "Old description")
        self.assertEqual(self.edits(), [])
        self.affected_mock.assert_not_called()

    def test_the_same_instant_with_a_utc_offset_is_not_an_edit(self):
        self.event()

        self.update(proposedStartAt=(START + timedelta(hours=8)).replace(tzinfo=timezone(timedelta(hours=8))))

        self.assertEqual(self.edits(), [])
        self.affected_mock.assert_not_called()

    def test_clearing_an_optional_field_is_logged(self):
        self.event(category="conference")

        updated = self.update(category=None)

        self.assertIsNone(updated.category)
        self.assertEqual((self.edits()[0].oldValue, self.edits()[0].newValue), ("conference", None))


class TestWhoCanEdit(UpdateCase):
    def test_only_the_assigned_coordinator_can_edit(self):
        self.event()

        with self.assertRaises(HTTPException) as ctx:
            self.update(caller="coord-2", description="Nope")

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.edits(), [])

    def test_completed_cancelled_rejected_draft_and_discarded_events_cannot_be_edited(self):
        for index, status in enumerate(("completed", "cancelled", "rejected", "draft", "discarded")):
            self.event(status=status, eventId=f"locked-{index}")

            with self.assertRaises(HTTPException) as ctx:
                self.update(event_id=f"locked-{index}", description="Nope")

            self.assertEqual(ctx.exception.status_code, 409, status)
            self.assertIn(status, ctx.exception.detail)
        self.assertEqual(self.edits(), [])

    def test_an_event_under_review_can_be_edited(self):
        self.event(status="under review")

        self.assertEqual(self.update(description="Clarified").description, "Clarified")

    def test_a_missing_event_is_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.update(event_id="missing", description="Nope")

        self.assertEqual(ctx.exception.status_code, 404)

    def test_the_end_must_stay_after_the_start(self):
        self.event()

        with self.assertRaises(HTTPException) as ctx:
            self.update(proposedStartAt=END)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(self.edits(), [])


class TestSignificantEdits(UpdateCase):
    def test_the_significant_and_quiet_fields_are_published(self):
        published = self.service.significant_fields()

        self.assertEqual(
            published.fields,
            [
                "proposedStartAt",
                "proposedEndAt",
                "expectedAttendance",
                "layoutPreference",
                "accessibilityNeeds",
                "equipmentRequirements",
            ],
        )
        self.assertEqual(published.quietFields, list(QUIET_FIELDS))
        self.assertFalse(set(SIGNIFICANT_FIELDS) & set(QUIET_FIELDS))

    def test_a_significant_edit_with_arrangements_names_them_and_saves_nothing_until_confirmed(self):
        self.event()
        self.affected_mock.return_value = [VENUE, EQUIPMENT]

        with self.assertRaises(HTTPException) as ctx:
            self.update(expectedAttendance=200, description="Bigger")

        self.assertEqual(ctx.exception.status_code, 409)
        detail = ctx.exception.detail
        self.assertTrue(detail["requiresConfirmation"])
        self.assertEqual(detail["significantFields"], ["expectedAttendance"])
        self.assertEqual(detail["arrangements"], [VENUE, EQUIPMENT])
        self.assertIsNone(detail["statusChange"])
        self.assertIn("expected attendance", detail["message"])
        self.assertIn("re-verification", detail["message"])
        self.affected_mock.assert_called_once_with("e1", "Bearer token")
        self.flag_mock.assert_not_called()
        stored = self.service.get_event("e1")
        self.assertEqual((stored.expectedAttendance, stored.description), (120, "Old description"))
        self.assertEqual(self.edits(), [])

    def test_a_confirmed_significant_edit_flags_the_arrangements_and_logs_each_field(self):
        self.event()
        self.flag_mock.return_value = [VENUE, EQUIPMENT]

        updated = self.update(expectedAttendance=200, layoutPreference="Banquet", confirmSignificantChange=True)

        self.assertEqual(updated.expectedAttendance, 200)
        self.assertEqual(updated.layoutPreference, "Banquet")
        self.assertEqual(updated.status, "planning")
        self.assertEqual([row.id for row in updated.flaggedArrangements], ["vb-1", "er-1"])
        event_id, reason, token = self.flag_mock.call_args.args
        self.assertEqual((event_id, token), ("e1", "Bearer token"))
        self.assertIn("Expected attendance: 120 -> 200", reason)
        self.assertIn("Layout: not set -> Banquet", reason)
        self.affected_mock.assert_not_called()
        edits = {edit.field: (edit.oldValue, edit.newValue) for edit in self.edits()}
        self.assertEqual(edits, {"expectedAttendance": ("120", "200"), "layoutPreference": (None, "Banquet")})

    def test_a_significant_edit_without_arrangements_on_a_planning_event_saves_straight_away(self):
        self.event()

        updated = self.update(accessibilityNeeds="Hearing loop")

        self.assertEqual(updated.accessibilityNeeds, "Hearing loop")
        self.affected_mock.assert_called_once()
        self.flag_mock.assert_not_called()

    def test_a_date_change_is_logged_in_iso_format(self):
        self.event()
        new_start = START + timedelta(days=7)

        self.update(proposedStartAt=new_start, proposedEndAt=END + timedelta(days=7), confirmSignificantChange=True)

        edits = {edit.field: (edit.oldValue, edit.newValue) for edit in self.edits()}
        self.assertEqual(edits["proposedStartAt"], (START.isoformat(), new_start.isoformat()))

    def test_arrangements_that_cannot_be_checked_stop_the_save(self):
        self.event()
        self.affected_mock.side_effect = service_unavailable("down")

        with self.assertRaises(HTTPException) as ctx:
            self.update(expectedAttendance=200)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(self.service.get_event("e1").expectedAttendance, 120)
        self.assertEqual(self.edits(), [])

    def test_arrangements_that_cannot_be_flagged_stop_the_save(self):
        self.event(status="confirmed")
        self.flag_mock.side_effect = service_unavailable("down")

        with self.assertRaises(HTTPException) as ctx:
            self.update(expectedAttendance=200, confirmSignificantChange=True)

        self.assertEqual(ctx.exception.status_code, 503)
        stored = self.service.get_event("e1")
        self.assertEqual((stored.expectedAttendance, stored.status), (120, "confirmed"))
        self.assertEqual(self.edits(), [])


class TestConfirmedEvents(UpdateCase):
    def test_a_significant_edit_on_a_confirmed_event_needs_confirmation_even_without_arrangements(self):
        self.event(status="confirmed")

        with self.assertRaises(HTTPException) as ctx:
            self.update(equipmentRequirements="Two more microphones")

        detail = ctx.exception.detail
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(detail["arrangements"], [])
        self.assertEqual(detail["statusChange"], {"from": "confirmed", "to": "reconsidering"})
        self.assertIn("no longer read as confirmed", detail["message"])
        self.assertEqual(self.service.get_event("e1").status, "confirmed")

    def test_a_confirmed_significant_edit_moves_the_event_to_reconsidering(self):
        self.event(status="confirmed")

        updated = self.update(expectedAttendance=180, confirmSignificantChange=True)

        self.assertEqual(updated.status, "reconsidering")
        self.assertEqual(self.service.get_event("e1").status, "reconsidering")
        history = self.db.query(EventStatusHistory).one()
        self.assertEqual((history.fromStatus, history.toStatus, history.changedBy), ("confirmed", "reconsidering", "coord-1"))
        self.assertIn("Expected attendance: 120 -> 180", history.note)

    def test_a_quiet_edit_keeps_a_confirmed_event_confirmed(self):
        self.event(status="confirmed")

        self.assertEqual(self.update(purpose="Clearer purpose").status, "confirmed")
        self.assertEqual(self.db.query(EventStatusHistory).count(), 0)

    def test_a_further_significant_edit_while_reconsidering_stays_reconsidering(self):
        self.event(status="reconsidering")

        updated = self.update(expectedAttendance=150, confirmSignificantChange=True)

        self.assertEqual(updated.status, "reconsidering")
        self.assertEqual(self.db.query(EventStatusHistory).count(), 0)


class TestActivityLogAndNotes(UpdateCase):
    def test_the_activity_log_lists_edits_before_the_status_change_they_caused(self):
        self.event(status="confirmed")
        self.update(expectedAttendance=180, confirmSignificantChange=True)

        log = self.service.get_activity_log("e1")

        self.assertEqual([entry.kind for entry in log], ["edit", "status"])
        self.assertEqual(
            (log[0].field, log[0].oldValue, log[0].newValue, log[0].changedBy),
            ("expectedAttendance", "120", "180", "coord-1"),
        )
        self.assertEqual((log[1].fromStatus, log[1].toStatus), ("confirmed", "reconsidering"))
        self.assertEqual(log[0].createdAt, log[1].createdAt)

    def test_internal_notes_are_left_out_of_the_shared_event_read(self):
        self.event(internalNotes="Client is sensitive about pricing")

        self.assertIsNone(self.service.get_event("e1").internalNotes)
        self.assertEqual(self.service.get_internal_notes("e1").internalNotes, "Client is sensitive about pricing")

    def test_internal_notes_are_empty_when_none_were_written(self):
        self.event()

        self.assertEqual(self.service.get_internal_notes("e1").internalNotes, "")
        self.assertEqual(self.update(description="Old description").internalNotes, "")

    def test_internal_notes_for_a_missing_event_are_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_internal_notes("missing")

        self.assertEqual(ctx.exception.status_code, 404)


class TestEventUpdateSchema(EventCase):
    def test_only_the_fields_sent_are_changed(self):
        body = EventUpdate(description="New", confirmSignificantChange=True)

        self.assertEqual(body.changed_values(), {"description": "New"})

    def test_required_fields_cannot_be_cleared(self):
        for field in ("eventName", "proposedStartAt", "expectedAttendance", "equipmentRequirements"):
            with self.assertRaises(ValidationError, msg=field):
                EventUpdate(**{field: None})

    def test_optional_fields_can_be_cleared(self):
        self.assertEqual(EventUpdate(category=None, layoutPreference=None).changed_values(), {"category": None, "layoutPreference": None})

    def test_the_end_must_be_after_the_start_when_both_are_sent(self):
        with self.assertRaises(ValidationError):
            EventUpdate(proposedStartAt=END, proposedEndAt=START)
        with self.assertRaises(ValidationError):
            EventUpdate(proposedStartAt=START, proposedEndAt=START)

    def test_an_offset_datetime_is_stored_as_naive_utc(self):
        body = EventUpdate(proposedStartAt=datetime(2026, 12, 1, 17, tzinfo=timezone(timedelta(hours=8))))

        self.assertEqual(body.proposedStartAt, datetime(2026, 12, 1, 9))

    def test_attendance_cannot_be_negative(self):
        with self.assertRaises(ValidationError):
            EventUpdate(expectedAttendance=-1)
