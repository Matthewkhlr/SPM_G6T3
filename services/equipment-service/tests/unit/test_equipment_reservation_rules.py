from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.schemas.equipment import EquipmentQuantityReserve, EquipmentRequestCreate
from shared.auth.deps import require_authenticated_user
from shared.testing.cases import ServiceTestCase
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create


class TestReservationRules(EquipmentCase):
    def test_reserve_refuses_more_than_is_available_and_logs_a_hold(self):
        created = self.service.create_equipment(equipment_create(totalQuantity=2), CALLER)
        with self.assertRaises(HTTPException) as ctx:
            self.service.reserve_quantity(
                EquipmentQuantityReserve(
                    eventId="e1", equipmentId=created.equipmentId, quantity=5, startsAt=START, endsAt=END
                ),
                CALLER,
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("2", str(ctx.exception.detail))

        reserved = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        self.assertEqual(reserved.quantity, 2)
        log = self.service.get_activity_log(created.equipmentId)
        self.assertTrue(any(entry.action == "reserve" for entry in log))

    def test_adjust_increase_is_capped_and_decrease_is_logged(self):
        created = self.service.create_equipment(equipment_create(code="ADJ", totalQuantity=4), CALLER)
        reserved = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        raised = self.service.adjust_reservation(reserved.reservationId, 3, CALLER)
        self.assertEqual(raised.quantity, 3)
        with self.assertRaises(HTTPException):
            self.service.adjust_reservation(reserved.reservationId, 9, CALLER)
        lowered = self.service.adjust_reservation(reserved.reservationId, 1, CALLER)
        self.assertEqual(lowered.quantity, 1)
        released = self.service.release_reservation(reserved.reservationId, CALLER, "no longer needed")
        self.assertEqual(released.status, "released")
        text = str(self.service.get_activity_log(created.equipmentId))
        self.assertIn("previousQuantity", text)
        self.assertIn("release", text)

    def test_a_confirmed_event_needs_a_reason_to_release(self):
        created = self.service.create_equipment(equipment_create(code="CNF", totalQuantity=2), CALLER)
        reserved = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        with patch("app.services.equipment_service._event_record", return_value={"status": "confirmed", "eventName": "Summit"}):
            with self.assertRaises(HTTPException) as ctx:
                self.service.release_reservation(reserved.reservationId, CALLER, "", "Bearer token")
            self.assertEqual(ctx.exception.status_code, 422)
            released = self.service.release_reservation(reserved.reservationId, CALLER, "panel failed", "Bearer token")
        self.assertEqual(released.status, "released")

    def test_a_finished_event_cannot_be_adjusted(self):
        created = self.service.create_equipment(equipment_create(code="END", totalQuantity=2), CALLER)
        reserved = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e9", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        with patch("app.services.equipment_service._event_record", return_value={"status": "rejected"}):
            with self.assertRaises(HTTPException) as ctx:
                self.service.adjust_reservation(reserved.reservationId, 2, CALLER, "Bearer token")
        self.assertEqual(ctx.exception.status_code, 409)

    def test_partial_unavailable_accept_amend_and_complete(self):
        created = self.service.create_equipment(equipment_create(code="PART", totalQuantity=2), CALLER)
        request = self.service.create_request(
            EquipmentRequestCreate(
                eventId="e3", equipmentId=created.equipmentId, quantity=4, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )
        partial = self.service.record_partial(request.requestId, 2, "Only two free", CALLER, None)
        self.assertEqual(partial.status, "partial")
        self.assertEqual(partial.shortfall, 2)
        self.assertEqual(partial.reservedQuantity, 2)
        accepted = self.service.accept_shortfall(request.requestId, COORDINATOR)
        self.assertEqual(accepted.status, "resolved")

        second = self.service.create_request(
            EquipmentRequestCreate(
                eventId="e3", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )
        marked = self.service.mark_unavailable(
            second.requestId, CALLER, "insufficient stock", "logged", None, "eq2"
        )
        self.assertEqual(marked.alternativeEquipmentId, "eq2")
        self.assertIn("stock", marked.decisionReason)
        amended = self.service.amend_request(second.requestId, 1)
        self.assertEqual(amended.status, "pending")
        completed = self.service.complete_review(second.requestId, CALLER)
        self.assertEqual(completed.status, "complete")
        log = str(self.service.get_activity_log(created.equipmentId))
        self.assertIn("unavailable", log)

    def test_full_reservation_notifies_and_a_shortfall_does_not(self):
        created = self.service.create_equipment(equipment_create(code="NOTE", totalQuantity=2), CALLER)
        self.service.create_request(
            EquipmentRequestCreate(
                eventId="e1", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )
        with patch("app.services.equipment_service._notify_people") as notify, patch(
            "app.services.equipment_service._event_record", return_value={"organiserContact": "amy@example.com"}
        ):
            self.service.reserve_quantity(
                EquipmentQuantityReserve(
                    eventId="e1", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
                ),
                CALLER,
                "Bearer token",
            )
            self.assertFalse(notify.called)
            self.service.reserve_quantity(
                EquipmentQuantityReserve(
                    eventId="e1", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
                ),
                CALLER,
                "Bearer token",
            )
            self.assertTrue(notify.called)

    def test_event_lookup_and_notify_swallow_a_down_service(self):
        from app.services.equipment_service import _event_record, _notify_people

        self.assertIsNone(_event_record("e1", None))
        failed = MagicMock()
        failed.status_code = 503
        with patch("app.services.equipment_service.httpx.get", return_value=failed):
            self.assertIsNone(_event_record("e1", "Bearer token"))
        with patch("app.services.equipment_service.httpx.get", side_effect=httpx.HTTPError("down")):
            self.assertIsNone(_event_record("e1", "Bearer token"))
        ok = MagicMock()
        ok.status_code = 200
        ok.json.return_value = {"status": "planning"}
        with patch("app.services.equipment_service.httpx.get", return_value=ok):
            self.assertEqual(_event_record("e1", "Bearer token")["status"], "planning")
        with patch("app.services.equipment_service.httpx.post", side_effect=httpx.HTTPError("down")):
            _notify_people("Subject", "Body", ["", "amy@example.com"], "Bearer token")
        _notify_people("Subject", "Body", [], None)

        created = self.service.create_equipment(equipment_create(code="GAP", totalQuantity=1), CALLER)
        request = self.service.create_request(
            EquipmentRequestCreate(
                eventId="e3", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )
        with self.assertRaises(HTTPException):
            self.service.record_partial(request.requestId, 4, "too many", CALLER, None)
        scarce = self.service.create_equipment(equipment_create(code="SCARCE", totalQuantity=1), CALLER)
        scarce_request = self.service.create_request(
            EquipmentRequestCreate(
                eventId="e3", equipmentId=scarce.equipmentId, quantity=2, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )
        with self.assertRaises(HTTPException) as available:
            self.service.record_partial(scarce_request.requestId, 2, "not enough", CALLER, None)
        self.assertIn("available", str(available.exception.detail))
        with self.assertRaises(HTTPException):
            self.service.accept_shortfall(request.requestId, COORDINATOR)
        held = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e3", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        self.service.release_reservation(held.reservationId, CALLER)
        with self.assertRaises(HTTPException):
            self.service.adjust_reservation(held.reservationId, 1, CALLER)
        self.assertEqual(self.service.get_reservation(held.reservationId).status, "released")
        outcomes = self.service.outcome_summary("e3")
        self.assertTrue(any(row["status"] == "released" for row in outcomes))
        closed = self.service.release_holds_for_event("e3", CALLER, "already released")
        self.assertEqual(closed, [])
        waiting = self.service.create_request(
            EquipmentRequestCreate(
                eventId="e-wait", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            COORDINATOR["userId"],
        )
        stored = self.service.request_dao.get_by_id(waiting.requestId)
        stored.status = "unavailable"
        stored.decisionReason = "maintenance"
        self.db.commit()
        waiting_outcomes = self.service.outcome_summary("e-wait")
        self.assertEqual(waiting_outcomes[0]["reservationId"], "")
        self.assertEqual(waiting_outcomes[0]["reason"], "maintenance")


class TestEquipmentArrangementRoutes(ServiceTestCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        self.assigned = patch("app.routers.equipment.fetch_event_coordinator", return_value=COORDINATOR["userId"])
        self.assigned.start()
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.caller.stop()
        self.assigned.stop()
        app.dependency_overrides.clear()
        super().tearDown()

    def test_partial_adjust_complete_and_resubmit_routes(self):
        created = self.client.post(
            "/equipment",
            headers=self.headers,
            json={"code": "ROUTE", "name": "Panel", "category": "display", "totalQuantity": 4},
        )
        equipment_id = created.json()["equipmentId"]
        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        request = self.client.post(
            "/equipment/requests",
            headers=self.headers,
            json={
                "eventId": "e3",
                "equipmentId": equipment_id,
                "quantity": 2,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        request_id = request.json()["requestId"]
        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        partial = self.client.post(
            f"/equipment/requests/{request_id}/partial",
            headers=self.headers,
            json={"reservedQuantity": 1, "reason": "One free"},
        )
        self.assertEqual(partial.status_code, 200)
        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR)
        self.caller.start()
        accepted = self.client.post(f"/equipment/requests/{request_id}/accept-shortfall", headers=self.headers)
        self.assertEqual(accepted.status_code, 200)
        resent = self.client.patch(
            f"/equipment/requests/{request_id}",
            headers=self.headers,
            json={"quantity": 1, "resubmit": True},
        )
        self.assertEqual(resent.status_code, 200)
        self.caller.stop()
        self.caller = patch("app.routers.equipment.resolve_caller", return_value=CALLER)
        self.caller.start()
        completed = self.client.post(f"/equipment/requests/{request_id}/complete-review", headers=self.headers)
        self.assertEqual(completed.status_code, 200)
        reserved = self.client.post(
            "/equipment/reservations",
            headers=self.headers,
            json={
                "eventId": "e3",
                "equipmentId": equipment_id,
                "quantity": 1,
                "startsAt": START.isoformat(),
                "endsAt": END.isoformat(),
            },
        )
        adjusted = self.client.patch(
            f"/equipment/reservations/{reserved.json()['reservationId']}",
            headers=self.headers,
            json={"quantity": 1},
        )
        self.assertEqual(adjusted.status_code, 200)
        fetched = self.client.get(
            f"/equipment/reservations/{reserved.json()['reservationId']}", headers=self.headers
        )
        self.assertEqual(fetched.status_code, 200)
        summary = self.client.get("/equipment/reservations/summary", headers=self.headers, params={"eventId": "e3"})
        self.assertEqual(summary.status_code, 200)
        self.assertTrue(summary.json())
        released = self.client.post(
            "/equipment/reservations/release-for-event",
            headers=self.headers,
            json={"eventId": "e3", "reason": "The event was closed"},
        )
        self.assertEqual(released.status_code, 200)
        self.assertEqual(released.json()[0]["status"], "released")
