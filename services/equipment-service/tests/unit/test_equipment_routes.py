from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import CALLER, COORDINATOR, END, START


class TestEquipmentRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_catalogue_request_and_reservation_routes(self):
        created = self.client.post(
            "/equipment",
            headers=self.headers,
            json={"code": "PX-200", "name": "Projector", "category": "display", "totalQuantity": 4},
        )
        self.assertEqual(created.status_code, 201)
        equipment_id = created.json()["equipmentId"]

        self.assertEqual(self.client.get("/equipment").status_code, 200)
        self.assertEqual(self.client.get(f"/equipment/{equipment_id}").status_code, 200)
        self.assertEqual(
            self.client.patch(
                f"/equipment/{equipment_id}",
                headers=self.headers,
                json={"name": "Projector Plus"},
            ).status_code,
            200,
        )
        self.assertEqual(self.client.get(f"/equipment/{equipment_id}/activity-log").status_code, 200)
        self.assertEqual(
            self.client.post(
                "/equipment/availability",
                json={"equipmentId": equipment_id, "startsAt": START.isoformat(), "endsAt": END.isoformat()},
            ).status_code,
            200,
        )
        reserved = self.client.post(
            "/equipment/reservations",
            headers=self.headers,
            json={
                "eventId": "e1",
                "equipmentId": equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        self.assertEqual(reserved.status_code, 201)
        self.assertEqual(self.client.post("/equipment/availability", json={}).status_code, 422)
        listed = self.client.get(f"/equipment/{equipment_id}/reservations", headers=self.headers)
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.json()[0]["status"], "active")

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        request = self.client.post(
            "/equipment/requests",
            headers=self.headers,
            json={
                "eventId": "e2",
                "equipmentId": equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        self.assertEqual(request.status_code, 201)
        requests = self.client.get("/equipment/requests", headers=self.headers)
        self.assertEqual(requests.status_code, 200)
        self.assertTrue(any(row["eventId"] == "e2" for row in requests.json()))
        checked = self.client.post("/equipment/availability", json={"eventId": "e2"})
        self.assertEqual(checked.status_code, 200)
        self.assertTrue(checked.json()["canMeet"])
        self.assertEqual(checked.json()["lines"][0]["requestedQuantity"], 1)
        self.assertEqual(checked.json()["lines"][0]["availableQuantity"], 3)

        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        self.assertEqual(
            self.client.post(
                f"/equipment/requests/{request.json()['requestId']}/review",
                headers=self.headers,
                json={"approve": True, "reviewNote": "OK"},
            ).status_code,
            200,
        )
        held = self.client.post(
            f"/equipment/requests/{request.json()['requestId']}/reserve",
            headers=self.headers,
        )
        self.assertEqual(held.status_code, 201)
        released = self.client.post(
            f"/equipment/reservations/{reserved.json()['reservationId']}/release",
            headers=self.headers,
            json={"reason": "done"},
        )
        self.assertEqual(released.status_code, 200)
        self.assertEqual(released.json()["status"], "released")
