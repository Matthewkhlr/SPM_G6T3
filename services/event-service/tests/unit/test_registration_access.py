from datetime import datetime

from fastapi import HTTPException

from tests.unit.support import COORDINATOR, ORGANISER, EventCase, insert_event

OPENS = datetime(2026, 9, 1, 0, 0)
CLOSES = datetime(2026, 10, 1, 0, 0)


def _viewer(user_id, role):
    return {"userId": user_id, "role": role}


class TestRegistrationAccess(EventCase):
    def setUp(self):
        super().setUp()
        insert_event(
            self.db,
            eventId="e1",
            organiserId="org-1",
            coordinatorId="coord-1",
            registrationEnabled=True,
            registrationOpensAt=OPENS,
            registrationClosesAt=CLOSES,
            capacity=50,
        )
        insert_event(
            self.db,
            eventId="e-other",
            organiserId="org-2",
            coordinatorId="coord-2",
            registrationEnabled=True,
            capacity=10,
        )
        insert_event(
            self.db,
            eventId="e-closed",
            organiserId="org-1",
            coordinatorId="coord-1",
            registrationEnabled=False,
            capacity=100,
        )
        insert_event(
            self.db,
            eventId="e-unassigned",
            organiserId="org-1",
            coordinatorId=None,
            registrationEnabled=True,
            capacity=8,
        )

    def test_the_organiser_can_read_capacity_and_the_registration_period(self):
        access = self.service.registration_access("e1", ORGANISER)

        self.assertEqual(access.eventId, "e1")
        self.assertEqual(access.capacity, 50)
        self.assertEqual(access.registrationOpensAt, OPENS)
        self.assertEqual(access.registrationClosesAt, CLOSES)
        self.assertNotIn("organiserId", access.model_dump())

    def test_the_assigned_coordinator_can_read_the_same_event(self):
        access = self.service.registration_access("e1", COORDINATOR)

        self.assertEqual(access.eventId, "e1")
        self.assertTrue(access.registrationEnabled)

    def test_access_is_for_that_event_only(self):
        own = self.service.registration_access("e1", ORGANISER)

        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e-other", ORGANISER)

        self.assertEqual(own.eventId, "e1")
        self.assertEqual(ctx.exception.status_code, 403)

    def test_another_organiser_is_refused_even_when_the_id_shares_a_prefix(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e1", _viewer("org-10", "organiser"))

        self.assertEqual(ctx.exception.status_code, 403)

    def test_another_coordinator_is_refused_even_when_the_id_shares_a_prefix(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e1", _viewer("coord-10", "coordinator"))

        self.assertEqual(ctx.exception.status_code, 403)

    def test_an_unassigned_coordinator_is_refused(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e-unassigned", COORDINATOR)

        self.assertEqual(ctx.exception.status_code, 403)

    def test_the_organiser_role_does_not_match_on_coordinator_id(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e-other", _viewer("coord-2", "organiser"))

        self.assertEqual(ctx.exception.status_code, 403)

    def test_the_coordinator_role_does_not_match_on_organiser_id(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e1", _viewer("org-1", "coordinator"))

        self.assertEqual(ctx.exception.status_code, 403)

    def test_other_roles_and_a_missing_user_are_refused(self):
        for caller in (
            _viewer("org-1", "venue"),
            _viewer("org-1", "techsupport"),
            _viewer("org-1", "attendee"),
            {"userId": "", "role": "organiser"},
            {"role": "organiser"},
        ):
            with self.assertRaises(HTTPException) as ctx:
                self.service.registration_access("e1", caller)
            self.assertEqual(ctx.exception.status_code, 403)

    def test_a_missing_event_is_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("missing", ORGANISER)

        self.assertEqual(ctx.exception.status_code, 404)

    def test_registration_access_is_not_offered_when_registration_is_disabled(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.registration_access("e-closed", ORGANISER)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Registration has not been enabled for this event.")
