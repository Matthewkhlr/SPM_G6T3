"""Role lookup from a Firebase identity over HTTP and SQL."""

from fastapi.testclient import TestClient

from app.main import app
from app.models.user import User
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase


class TestUserWorkflow(ServiceTestCase):
    def test_an_unknown_token_is_refused_and_a_linked_account_returns_its_role(self):
        client = TestClient(app)
        client.__enter__()
        try:
            self.assertEqual(client.get("/users/me").status_code, 401)
            self.db.add(
                User(
                    userId="u5",
                    email="amy@example.com",
                    userName="Amy Wong",
                    role="attendee",
                    firebaseUid="uid-amy",
                )
            )
            self.db.commit()
            app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-amy", "email": "amy@example.com"}
            me = client.get("/users/me", headers={"Authorization": "Bearer token"})
            self.assertEqual(me.status_code, 200)
            self.assertEqual(me.json()["role"], "attendee")
            directory = client.get("/users", headers={"Authorization": "Bearer token"})
            self.assertEqual(directory.status_code, 200)
            self.assertEqual(directory.json()[0]["userId"], "u5")
        finally:
            client.__exit__(None, None, None)
            app.dependency_overrides.clear()
