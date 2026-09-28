from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import confirmed_event, make_window


class TestRegistrationRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {
            "uid": "uid-1",
            "email": "amy@connectsphere.com",
        }
        self.lookup = patch("app.services.registration_service._event", return_value=confirmed_event())
        self.lookup.start()
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
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
        listed = self.client.get("/registrations", params={"eventId": "e1"})

        self.assertEqual(created.status_code, 201)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(len(listed.json()), 1)
