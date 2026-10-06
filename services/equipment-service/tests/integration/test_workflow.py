"""Catalogue, reservation, shortfall, and release over HTTP and SQL."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase

TECH = {"userId": "u-tech", "userName": "Cara", "role": "techsupport"}
COORDINATOR = {"userId": "u-coord", "userName": "Ben", "role": "coordinator"}


class TestEquipmentWorkflow(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=TECH)
        self.assigned = patch("app.routers.equipment.fetch_event_coordinator", return_value=COORDINATOR["userId"])
        self.caller.start()
        self.assigned.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.assigned.stop()
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_reserve_shortfall_adjust_and_release(self):
        gate = app.dependency_overrides.pop(require_authenticated_user)
        self.assertEqual(self.client.get("/equipment").status_code, 401)
        app.dependency_overrides[require_authenticated_user] = gate
        created = self.client.post(
            "/equipment",
            headers=self.headers,
            json={"code": "PX", "name": "Projector", "category": "display", "totalQuantity": 2},
        )
        self.assertEqual(created.status_code, 201)
        equipment_id = created.json()["equipmentId"]
        window = {"startsAt": "2026-12-01T09:00:00", "endsAt": "2026-12-01T17:00:00"}

        refused = self.client.post(
            "/equipment/reservations",
            headers=self.headers,
            json={"eventId": "e1", "equipmentId": equipment_id, "quantity": 5, **window},
        )
        self.assertEqual(refused.status_code, 409)

        reserved = self.client.post(
            "/equipment/reservations",
            headers=self.headers,
            json={"eventId": "e1", "equipmentId": equipment_id, "quantity": 1, **window},
        )
        self.assertEqual(reserved.status_code, 201)
        reservation_id = reserved.json()["reservationId"]

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        request = self.client.post(
            "/equipment/requests",
            headers=self.headers,
            json={"eventId": "e1", "equipmentId": equipment_id, "quantity": 2, **window},
        )
        self.assertEqual(request.status_code, 201)
        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=TECH)
        self.caller.start()

        partial = self.client.post(
            f"/equipment/requests/{request.json()['requestId']}/partial",
            headers=self.headers,
            json={"reservedQuantity": 1, "reason": "One free"},
        )
        self.assertEqual(partial.status_code, 200)
        self.assertEqual(partial.json()["shortfall"], 1)

        adjusted = self.client.patch(
            f"/equipment/reservations/{reservation_id}",
            headers=self.headers,
            json={"quantity": 1},
        )
        self.assertEqual(adjusted.status_code, 200)
        released = self.client.post(
            f"/equipment/reservations/{reservation_id}/release",
            headers=self.headers,
            json={"reason": "panel failed inspection"},
        )
        self.assertEqual(released.status_code, 200)
        log = self.client.get(f"/equipment/{equipment_id}/activity-log")
        self.assertIn("reserve", str(log.json()))
        self.assertIn("release", str(log.json()))
