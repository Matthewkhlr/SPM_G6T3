from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import seed_user


class TestUserRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {
            "uid": "firebase-uid-1",
            "email": "amy@connectsphere.com",
        }
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_me_links_the_firebase_uid_and_returns_the_profile(self):
        seed_user(self.db)

        response = self.client.get("/users/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["userId"], "u-1")

    def test_me_returns_404_when_the_token_matches_nobody(self):
        response = self.client.get("/users/me")

        self.assertEqual(response.status_code, 404)

    def test_list_users_returns_the_directory(self):
        seed_user(self.db)
        seed_user(self.db, userId="u-2", email="ben@connectsphere.com", userName="Ben")

        response = self.client.get("/users")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 2)
