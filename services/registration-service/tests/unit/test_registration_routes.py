from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.attendee_registration import AttendeeRegistration
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import confirmed_event, make_window

class SilentClient:
    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def post(self, url, json=None, headers=None):
        return None


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
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(
                proposedStartAt=(datetime.utcnow() + timedelta(days=3)).isoformat(),
            ),
        )
        self.access = patch(
            "app.services.registration_service._registration_access",
            return_value=ACCESS,
        )
        self.identity = patch("app.routers.registration.resolve_caller")
        self.notify = patch("app.services.registration_service.httpx.Client", SilentClient)
        self.lookup.start()
        self.access.start()
        self.notify.start()
        self.resolve_caller = self.identity.start()
        self.resolve_caller.return_value = {
            "userId": "u-org",
            "role": "organiser",
            "email": "amy@example.com",
        }
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.identity.stop()
        self.notify.stop()
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
        self.assertEqual(body["remainingPlaces"], 9)
        self.assertEqual(body["placesRemaining"], 9)
        stored = self.db.get(AttendeeRegistration, created.json()["attendeeRegistrationId"])
        self.assertEqual(stored.userId, "u-org")
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

    def _register(self, email="guest@example.com", name="Guest"):
        make_window(self.db)
        self.resolve_caller.return_value = {
            "userId": "u-att",
            "role": "attendee",
            "email": "attendee2@connectsphere.com",
        }
        created = self.client.post(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            json={"eventId": "e1", "name": name, "email": email},
        )
        self.assertEqual(created.status_code, 201)
        return created.json()

    def test_an_attendee_sees_remaining_places_without_other_names(self):
        created = self._register()
        places = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )

        self.assertEqual(places.status_code, 200)
        body = places.json()
        self.assertEqual(body["attendees"], [])
        self.assertEqual(body["remainingPlaces"], body["placesRemaining"])
        self.assertNotIn("guest@example.com", places.text)
        self.assertEqual(created["attendeeEmail"], "guest@example.com")

    def test_withdraw_keeps_the_row_releases_one_place_and_allows_registering_again(self):
        created = self._register()
        before = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )
        self.resolve_caller.return_value = {
            "userId": "u-other",
            "role": "attendee",
            "email": "other@example.com",
        }
        denied = self.client.post(
            f"/registrations/{created['attendeeRegistrationId']}/withdraw",
            headers={"Authorization": "Bearer token"},
        )
        self.assertEqual(denied.status_code, 403)

        self.resolve_caller.return_value = {
            "userId": "u-att",
            "role": "attendee",
            "email": "attendee2@connectsphere.com",
        }
        withdrawn = self.client.post(
            f"/registrations/{created['attendeeRegistrationId']}/withdraw",
            headers={"Authorization": "Bearer token"},
        )
        viewed = self.client.get(
            f"/registrations/{created['attendeeRegistrationId']}",
            headers={"Authorization": "Bearer token"},
        )
        after = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )
        again = self.client.post(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            json={"eventId": "e1", "name": "Guest", "email": "guest@example.com"},
        )
        missing = self.client.post(
            "/registrations/missing/withdraw",
            headers={"Authorization": "Bearer token"},
        )
        mine = self.client.get("/registrations/mine", headers={"Authorization": "Bearer token"})

        self.assertEqual(withdrawn.status_code, 200)
        self.assertEqual(withdrawn.json()["status"], "withdrawn")
        self.assertIsNotNone(withdrawn.json()["withdrawnAt"])
        self.assertEqual(viewed.status_code, 200)
        self.assertEqual(viewed.json()["status"], "withdrawn")
        self.assertEqual(after.json()["remainingPlaces"], before.json()["remainingPlaces"] + 1)
        self.assertNotIn("guest@example.com", after.text)
        self.assertEqual(again.status_code, 201)
        self.assertNotEqual(again.json()["attendeeRegistrationId"], created["attendeeRegistrationId"])
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(
            {row["attendeeRegistrationId"] for row in mine.json()},
            {created["attendeeRegistrationId"], again.json()["attendeeRegistrationId"]},
        )
        self.assertEqual(self.db.get(AttendeeRegistration, created["attendeeRegistrationId"]).status, "withdrawn")

    def test_withdraw_is_refused_when_the_event_has_started_or_been_cancelled(self):
        created = self._register()
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(
                status="cancelled",
                proposedStartAt=(datetime.utcnow() + timedelta(days=3)).isoformat(),
            ),
        )
        self.lookup.start()

        refused = self.client.post(
            f"/registrations/{created['attendeeRegistrationId']}/withdraw",
            headers={"Authorization": "Bearer token"},
        )

        self.assertEqual(refused.status_code, 409)
        self.assertEqual(self.db.get(AttendeeRegistration, created["attendeeRegistrationId"]).status, "registered")

    def test_a_disabled_registration_does_not_give_an_attendee_the_places(self):
        self._register()
        self.lookup.stop()
        self.lookup = patch(
            "app.services.registration_service._event",
            return_value=confirmed_event(registrationEnabled=False),
        )
        self.lookup.start()

        denied = self.client.get(
            "/registrations",
            headers={"Authorization": "Bearer token"},
            params={"eventId": "e1"},
        )

        self.assertEqual(denied.status_code, 404)
        self.assertNotIn("guest@example.com", denied.text)

    def test_mine_is_empty_when_the_caller_has_no_identity(self):
        self.resolve_caller.return_value = {"userId": "", "role": "attendee", "email": ""}

        mine = self.client.get("/registrations/mine", headers={"Authorization": "Bearer token"})

        self.assertEqual(mine.status_code, 200)
        self.assertEqual(mine.json(), [])
