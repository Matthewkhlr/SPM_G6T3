from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.models.event_field_change import EventFieldChange
from app.schemas.event import RegistrationSettingsUpdate
from app.services.event_service import REGISTRATION_SETUP_STATUSES
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import service_unavailable
from shared.testing.cases import ServiceTestCase
from tests.unit.support import EventCase, insert_event

START = datetime(2026, 12, 1, 9)
OPENS = datetime(2026, 11, 1, 9)
CLOSES = datetime(2026, 11, 20, 18)
DIRECTORY = [
    {"userId": "coord-1", "userName": "Ben Lee", "email": "ben@connectsphere.com", "role": "coordinator"},
    {"userId": "org-1", "userName": "Amy", "email": "amy@apex.com", "role": "organiser", "organisationId": "o1"},
]
MARINA = {"venueName": "Marina Hall A", "layout": "Theatre", "capacity": 300}
ATTENDEES = [
    {"userId": "att-1", "attendeeEmail": "one@example.com", "status": "registered"},
    {"userId": None, "attendeeEmail": "guest@example.com", "status": "registered"},
]
HEADERS = {"Authorization": "Bearer token"}


class SettingsCase(EventCase):
    def setUp(self):
        super().setUp()
        self.patches = {
            "names": patch("app.services.event_service.organisation_names", return_value={}),
            "users": patch("app.services.event_service.list_users", return_value=DIRECTORY),
            "email": patch("app.services.event_service.send_notification", return_value=True),
            "inbox": patch("app.services.event_service.record_notification", return_value=True),
            "registered": patch("app.services.event_service.current_registration_count", return_value=0),
            "venues": patch("app.services.event_service.booked_venue_capacities", return_value=[]),
            "attendees": patch("app.services.event_service.registered_attendees", return_value=ATTENDEES),
        }
        self.mocks = {name: p.start() for name, p in self.patches.items()}

    def tearDown(self):
        for p in self.patches.values():
            p.stop()
        super().tearDown()

    def event(self, status="planning", coordinatorId="coord-1", **overrides):
        values = dict(eventName="Summit", proposedStartAt=START, layoutPreference="Theatre", capacity=3)
        values.update(overrides)
        return insert_event(self.db, eventId="e1", status=status, coordinatorId=coordinatorId, **values)

    def save(self, coordinator_id="coord-1", event_id="e1", **body):
        return self.service.update_registration_settings(
            event_id, RegistrationSettingsUpdate(**body), coordinator_id, "Bearer token"
        )

    def refused(self, **body) -> HTTPException:
        with self.assertRaises(HTTPException) as ctx:
            self.save(**body)
        return ctx.exception

    def stored(self):
        return self.service.get_event("e1")

    def logged(self):
        return {row.field: (row.oldValue, row.newValue, row.changedBy) for row in self.db.query(EventFieldChange)}


class TestSettingUp(SettingsCase):
    """AC1."""

    def test_the_assigned_coordinator_sets_registration_needed_period_and_capacity(self):
        self.event()

        saved = self.save(registrationEnabled=True, registrationOpensAt=OPENS, registrationClosesAt=CLOSES, capacity=80)

        self.assertEqual(
            (saved.registrationEnabled, saved.registrationOpensAt, saved.registrationClosesAt, saved.capacity),
            (True, OPENS, CLOSES, 80),
        )
        self.assertEqual(self.stored().capacity, 80)

    def test_only_the_fields_sent_change(self):
        self.event(registrationEnabled=True, registrationOpensAt=OPENS, registrationClosesAt=CLOSES)

        saved = self.save(capacity=50)

        self.assertEqual((saved.registrationEnabled, saved.registrationOpensAt, saved.capacity), (True, OPENS, 50))

    def test_every_status_from_planning_to_confirmed_is_allowed(self):
        for index, status in enumerate(REGISTRATION_SETUP_STATUSES):
            insert_event(self.db, eventId=f"e-{index}", status=status, coordinatorId="coord-1", proposedStartAt=START)
            with self.subTest(status=status):
                self.assertEqual(self.save(event_id=f"e-{index}", capacity=10).capacity, 10)

    def test_before_planning_or_after_confirmed_is_refused(self):
        for index, status in enumerate(("under review", "changes requested", "completed", "cancelled", "rejected")):
            insert_event(self.db, eventId=f"e-{index}", status=status, coordinatorId="coord-1", proposedStartAt=START)
            with self.subTest(status=status), self.assertRaises(HTTPException) as ctx:
                self.save(event_id=f"e-{index}", capacity=10)
            self.assertEqual(ctx.exception.status_code, 409)
            self.assertIn("from planning until the event is confirmed", ctx.exception.detail)

    def test_only_the_assigned_coordinator(self):
        self.event()
        self.assertEqual(self.refused(coordinator_id="coord-2", capacity=10).status_code, 403)
        insert_event(self.db, eventId="e-unassigned", status="planning", coordinatorId=None)
        self.assertEqual(self.refused(event_id="e-unassigned", capacity=10).status_code, 409)

    def test_a_missing_event_is_404(self):
        self.assertEqual(self.refused(capacity=10).status_code, 404)

    def test_needed_and_capacity_cannot_be_cleared_and_times_are_stored_in_utc_to_the_second(self):
        for body in ({"capacity": None}, {"registrationEnabled": None}, {"capacity": -1}):
            with self.subTest(body=body), self.assertRaises(ValidationError):
                RegistrationSettingsUpdate(**body)
        aware = datetime(2026, 11, 1, 17, 0, 0, 123456, tzinfo=timezone(timedelta(hours=8)))
        self.assertEqual(RegistrationSettingsUpdate(registrationOpensAt=aware).registrationOpensAt, datetime(2026, 11, 1, 9))
        self.assertEqual(
            RegistrationSettingsUpdate(registrationOpensAt=None, capacity=5, confirmRegistrationOff=True).changed_values(),
            {"registrationOpensAt": None, "capacity": 5},
        )


class TestPeriod(SettingsCase):
    """AC2."""

    def test_closing_must_be_after_opening(self):
        self.event()

        for closes in (OPENS, OPENS - timedelta(hours=1)):
            with self.subTest(closes=closes):
                error = self.refused(registrationOpensAt=OPENS, registrationClosesAt=closes)
                self.assertEqual((error.status_code, error.detail), (422, "Registration must close after it opens"))
        self.assertIsNone(self.stored().registrationOpensAt)

    def test_closing_must_be_no_later_than_the_event_start(self):
        self.event()

        error = self.refused(registrationClosesAt=START + timedelta(minutes=1))

        self.assertEqual(error.status_code, 422)
        self.assertIn("no later than the event starts", error.detail)
        self.assertEqual(self.save(registrationClosesAt=START).registrationClosesAt, START)

    def test_one_end_is_checked_against_the_stored_other(self):
        self.event(registrationOpensAt=OPENS, registrationClosesAt=CLOSES)

        self.assertEqual(self.refused(registrationClosesAt=OPENS).status_code, 422)
        self.assertEqual(self.refused(registrationOpensAt=CLOSES).status_code, 422)

    def test_the_period_can_be_cleared_while_it_is_still_being_decided(self):
        self.event(registrationOpensAt=OPENS, registrationClosesAt=CLOSES)

        saved = self.save(registrationOpensAt=None, registrationClosesAt=None)

        self.assertEqual((saved.registrationOpensAt, saved.registrationClosesAt), (None, None))


class TestVenueCapacity(SettingsCase):
    """AC3."""

    def test_a_capacity_above_the_booked_venue_warns_with_both_figures_and_saves_nothing(self):
        self.mocks["venues"].return_value = [MARINA]
        self.event()

        error = self.refused(capacity=500)

        self.assertEqual(error.status_code, 409)
        self.assertTrue(error.detail["requiresConfirmation"])
        [warning] = error.detail["warnings"]
        self.assertEqual(
            (warning["kind"], warning["capacity"], warning["venueCapacity"], warning["layout"]),
            ("venueCapacity", 500, 300, "Theatre"),
        )
        self.assertEqual(error.detail["message"], "A capacity of 500 is more than Marina Hall A holds in the Theatre layout (300).")
        self.mocks["venues"].assert_called_once_with("e1", "Theatre", "Bearer token")
        self.assertEqual(self.stored().capacity, 3)
        self.assertEqual(self.logged(), {})

    def test_once_confirmed_it_saves_without_asking_the_venue_again(self):
        self.mocks["venues"].return_value = [MARINA]
        self.event()

        self.assertEqual(self.save(capacity=500, confirmOverVenueCapacity=True).capacity, 500)
        self.mocks["venues"].assert_not_called()

    def test_a_venue_with_no_matching_layout_is_named_by_its_largest_capacity(self):
        self.mocks["venues"].return_value = [{**MARINA, "layout": None, "capacity": 320}]
        self.event()

        self.assertEqual(self.refused(capacity=400).detail["message"], "A capacity of 400 is more than Marina Hall A holds (320).")

    def test_a_capacity_the_venue_holds_or_no_confirmed_booking_saves_straight_away(self):
        self.event()
        self.assertEqual(self.save(capacity=500).capacity, 500)
        self.mocks["venues"].return_value = [MARINA]
        self.assertEqual(self.save(capacity=300).capacity, 300)

    def test_an_unchanged_capacity_above_the_venue_is_still_checked(self):
        self.mocks["venues"].return_value = [MARINA]
        self.event(capacity=500)

        self.assertEqual(self.refused(capacity=500).status_code, 409)

    def test_an_unreachable_venue_service_saves_nothing(self):
        self.mocks["venues"].side_effect = service_unavailable("venue down")
        self.event()

        self.assertEqual(self.refused(capacity=50).status_code, 503)
        self.assertEqual(self.stored().capacity, 3)


class TestRegisteredCount(SettingsCase):
    """AC4."""

    def test_a_capacity_below_the_registered_count_is_refused_stating_the_count(self):
        self.mocks["registered"].return_value = 3
        self.event()

        error = self.refused(capacity=2, confirmOverVenueCapacity=True)

        self.assertEqual(error.status_code, 409)
        self.assertEqual(error.detail["registeredCount"], 3)
        self.assertEqual(error.detail["message"], "3 people are already registered, so the capacity cannot go below 3.")
        self.assertNotIn("requiresConfirmation", error.detail)
        self.assertEqual(self.stored().capacity, 3)

    def test_one_registration_reads_as_one_person_and_matching_it_is_allowed(self):
        self.mocks["registered"].return_value = 1
        self.event()

        self.assertIn("1 person is already registered", self.refused(capacity=0).detail["message"])
        self.assertEqual(self.save(capacity=1).capacity, 1)

    def test_the_count_is_only_read_when_capacity_or_turning_off_needs_it(self):
        self.event()

        self.save(registrationOpensAt=OPENS)

        self.mocks["registered"].assert_not_called()

    def test_an_unreachable_registration_service_saves_nothing(self):
        self.mocks["registered"].side_effect = service_unavailable("registrations down")
        self.event()

        self.assertEqual(self.refused(capacity=50).status_code, 503)


class TestTurningOff(SettingsCase):
    """AC5."""

    def test_turning_off_with_people_registered_warns_and_saves_nothing(self):
        self.mocks["registered"].return_value = 2
        self.event(registrationEnabled=True)

        error = self.refused(registrationEnabled=False)

        self.assertEqual(error.status_code, 409)
        [warning] = error.detail["warnings"]
        self.assertEqual((warning["kind"], warning["registeredCount"]), ("registrationOff", 2))
        self.assertIn("2 attendees are already registered", error.detail["message"])
        self.assertTrue(self.stored().registrationEnabled)
        self.mocks["attendees"].assert_not_called()

    def test_once_confirmed_registration_is_off_and_every_registered_attendee_is_told(self):
        self.mocks["registered"].return_value = 2
        self.event(registrationEnabled=True)

        saved = self.save(registrationEnabled=False, confirmRegistrationOff=True)

        self.assertEqual((saved.registrationEnabled, saved.notifiedAttendees), (False, 2))
        emailed = [call.args[0] for call in self.mocks["email"].call_args_list]
        self.assertIn("one@example.com", emailed)
        self.assertIn("guest@example.com", emailed)
        inboxes = {call.args[0]: call.args[2] for call in self.mocks["inbox"].call_args_list}
        self.assertEqual(inboxes["att-1"], "registration.closed")
        self.assertNotIn(None, inboxes)

    def test_one_registration_reads_as_one_attendee(self):
        self.mocks["registered"].return_value = 1
        self.event(registrationEnabled=True)

        self.assertIn("1 attendee is already registered", self.refused(registrationEnabled=False).detail["message"])

    def test_turning_off_with_nobody_registered_needs_no_confirmation(self):
        self.event(registrationEnabled=True)

        saved = self.save(registrationEnabled=False)

        self.assertEqual((saved.registrationEnabled, saved.notifiedAttendees), (False, 0))
        self.mocks["attendees"].assert_not_called()

    def test_sending_off_for_an_event_already_off_is_not_turning_it_off(self):
        self.mocks["registered"].return_value = 2
        self.event(registrationEnabled=False)

        self.assertEqual(self.save(registrationEnabled=False).notifiedAttendees, 0)
        self.mocks["registered"].assert_not_called()

    def test_both_warnings_come_back_together(self):
        self.mocks["registered"].return_value = 2
        self.mocks["venues"].return_value = [MARINA]
        self.event(registrationEnabled=True)

        error = self.refused(registrationEnabled=False, capacity=500)

        self.assertEqual([warning["kind"] for warning in error.detail["warnings"]], ["venueCapacity", "registrationOff"])


class TestOrganiserTold(SettingsCase):
    """AC6."""

    def test_the_organiser_is_emailed_and_notified_in_app_with_what_changed(self):
        self.event()

        self.save(registrationEnabled=True, registrationOpensAt=OPENS, capacity=60)

        to, subject, body, _ = self.mocks["email"].call_args.args
        self.assertEqual((to, subject), ("amy@apex.com", "Registration settings changed for Summit"))
        self.assertIn("Registration: needed; Registration opens: 01 Nov 2026, 09:00; Capacity: 60.", body)
        user_id, event_id, kind, title, in_app, _ = self.mocks["inbox"].call_args.args
        self.assertEqual((user_id, event_id, kind, title, in_app), ("org-1", "e1", "event.registration_settings", subject, body))

    def test_a_cleared_or_turned_off_setting_reads_plainly(self):
        self.event(registrationEnabled=True, registrationOpensAt=OPENS)

        self.save(registrationEnabled=False, registrationOpensAt=None)

        self.assertIn("Registration: not needed; Registration opens: not set.", self.mocks["email"].call_args.args[2])

    def test_nothing_changed_tells_nobody(self):
        self.event(capacity=60)

        self.save(capacity=60)

        self.mocks["email"].assert_not_called()
        self.mocks["inbox"].assert_not_called()

    def test_an_unreachable_directory_still_leaves_the_in_app_notice(self):
        self.mocks["users"].side_effect = service_unavailable("down")
        self.event()

        self.save(capacity=60)

        self.mocks["email"].assert_not_called()
        self.assertEqual(self.mocks["inbox"].call_args.args[0], "org-1")


class TestActivityLog(SettingsCase):
    """AC7."""

    def test_each_changed_setting_is_logged_with_old_and_new_values_and_who(self):
        self.event(capacity=3)

        self.save(registrationEnabled=True, registrationOpensAt=OPENS, capacity=70, registrationClosesAt=None)

        self.assertEqual(
            self.logged(),
            {
                "registrationEnabled": ("False", "True", "coord-1"),
                "registrationOpensAt": (None, OPENS.isoformat(), "coord-1"),
                "capacity": ("3", "70", "coord-1"),
            },
        )
        entries = [entry for entry in self.service.get_activity_log("e1") if entry.kind == "edit"]
        self.assertEqual({entry.field for entry in entries}, {"registrationEnabled", "registrationOpensAt", "capacity"})


class TestRegistrationSettingsRoute(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.patches = [
            patch("app.services.event_service.registration_count", return_value=0),
            patch("app.services.event_service.organisation_names", return_value={}),
            patch("app.services.event_service.list_users", return_value=DIRECTORY),
            patch("app.services.event_service.send_notification", return_value=True),
            patch("app.services.event_service.record_notification", return_value=True),
            patch("app.services.event_service.current_registration_count", return_value=2),
            patch("app.services.event_service.booked_venue_capacities", return_value=[MARINA]),
        ]
        for p in self.patches:
            p.start()
        self.caller = patch(
            "app.routers.event.resolve_caller", return_value={"userId": "coord-1", "role": "coordinator"}
        )
        self.caller_mock = self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        insert_event(self.db, eventId="e1", status="confirmed", coordinatorId="coord-1", proposedStartAt=START, layoutPreference="Theatre")

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        for p in reversed(self.patches):
            p.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def patch_settings(self, body):
        return self.client.patch("/events/e1/registration-settings", headers=HEADERS, json=body)

    def test_set_warn_confirm_and_refuse(self):
        saved = self.patch_settings(
            {"registrationEnabled": True, "registrationOpensAt": "2026-11-01T01:00:00Z", "registrationClosesAt": "2026-11-20T10:00:00Z", "capacity": 80}
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual((saved.json()["capacity"], saved.json()["registrationOpensAt"]), (80, "2026-11-01T01:00:00"))
        self.assertEqual(self.caller_mock.call_args.kwargs["allowed_roles"], {"coordinator"})

        warned = self.patch_settings({"capacity": 500})
        self.assertEqual(warned.status_code, 409)
        self.assertIn("500", warned.json()["detail"]["message"])
        self.assertEqual(self.patch_settings({"capacity": 500, "confirmOverVenueCapacity": True}).status_code, 200)

        self.assertEqual(self.patch_settings({"capacity": 1}).status_code, 409)
        self.assertEqual(self.patch_settings({"registrationClosesAt": "2026-12-02T00:00:00"}).status_code, 422)
        self.assertEqual(self.patch_settings({"capacity": None}).status_code, 422)

        log = self.client.get("/events/e1/activity-log", headers=HEADERS).json()
        self.assertIn("capacity", {entry.get("field") for entry in log})
