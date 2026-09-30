from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.attendee_registration import AttendeeRegistration
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import confirmed_event, make_window

ACCESS = {
    "eventId": "e1",
    "registrationEnabled": True,
    "registrationOpensAt": "2026-09-01T00:00:00",
    "registrationClosesAt": "2026-10-01T00:00:00",
    "capacity": 10,
}


class TestRegistrationRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {
            "uid": "uid-1",
            "email": "amy@connectsphere.com",
        }
        self.lookup = patch("app.services.registration_service._event", return_value=confirmed_event())
        self.access = patch(
            "app.services.registration_service._registration_access",
            return_value=ACCESS,
        )
        self.lookup.start()
        self.access.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.access.stop()
        self.lookup.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_post_and_get_registrations(self):
        make_window(self.db)

        created = self.client.post(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            json={"eventId": "e1", "name": "Amy Wong", "email": "amy@example.com"},
        )
        listed = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )
        counted = self.client.get("/registrations/count", params={"eventId": "e1"})

        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["status"], "registered")
        self.assertIsNotNone(created.json()["createdAt"])
        self.assertEqual(listed.status_code, 200)
        body = listed.json()
        self.assertEqual(body["registered"], 1)
        self.assertEqual(body["remaining"], 9)
        self.assertEqual(body["attendees"][0]["attendeeName"], "Amy Wong")
        self.assertEqual(body["attendees"][0]["attendeeEmail"], "amy@example.com")
        self.assertEqual(counted.status_code, 200)
        self.assertEqual(counted.json(), {"count": 1})
        self.assertNotIn("amy@example.com", counted.text)

    def test_get_can_hide_withdrawn_rows(self):
        make_window(self.db)
        self.client.post(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            json={"eventId": "e1", "name": "Amy Wong", "email": "amy@example.com"},
        )
        withdrawn = self.db.query(AttendeeRegistration).one()
        withdrawn.status = "withdrawn"
        self.db.commit()

        listed = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1", "includeWithdrawn": False},
        )

        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()["attendees"], [])
        self.assertEqual(listed.json()["withdrawn"], 1)
        self.assertEqual(listed.json()["registered"], 0)

    def test_get_refuses_a_caller_the_event_service_rejects(self):
        make_window(self.db)
        self.access.stop()
        self.access = patch(
            "app.services.registration_service._registration_access",
            side_effect=HTTPException(
                status_code=403,
                detail="You do not have permission to view these registrations.",
            ),
        )
        self.access.start()

        denied = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )

        self.assertEqual(denied.status_code, 403)
        self.assertNotIn("attendees", denied.json())

    def test_get_is_not_found_when_registration_is_disabled(self):
        self.access.stop()
        self.access = patch(
            "app.services.registration_service._registration_access",
            return_value={**ACCESS, "registrationEnabled": False},
        )
        self.access.start()

        denied = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )

        self.assertEqual(denied.status_code, 404)
