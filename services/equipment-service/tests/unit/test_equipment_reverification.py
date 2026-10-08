from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.equipment import EquipmentAvailabilityIn, EquipmentQuantityReserve
from shared.auth.deps import require_authenticated_user
from shared.exceptions.http import forbidden
from tests.unit.support import CALLER, COORDINATOR, END, START, EquipmentCase, equipment_create


class ReverificationCase(EquipmentCase):
    def setUp(self):
        super().setUp()
        self.equipment_id = self.service.create_equipment(equipment_create(totalQuantity=5), CALLER).equipmentId

    def reserve(self, event_id="e1", quantity=1):
        return self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId=event_id, equipmentId=self.equipment_id, quantity=quantity, startsAt=START, endsAt=END
            ),
            CALLER,
        ).reservationId


class TestReservationReverification(ReverificationCase):
    def test_only_the_events_held_reservations_are_flagged_and_keep_their_status(self):
        held = self.reserve()
        released = self.reserve()
        self.service.release_reservation(released, CALLER)
        other_event = self.reserve(event_id="e2")

        flagged = self.service.flag_for_reverification("e1", "Expected attendance: 20 -> 200")

        self.assertEqual([row.reservationId for row in flagged], [held])
        self.assertTrue(flagged[0].needsReverification)
        self.assertEqual(flagged[0].status, "active")
        self.assertEqual(flagged[0].reverificationNote, "Expected attendance: 20 -> 200")
        self.assertEqual(flagged[0].equipmentName, "Projector")
        by_id = {row.reservationId: row for row in self.service.list_event_reservations("e1")}
        self.assertEqual(set(by_id), {held, released})
        self.assertFalse(by_id[released].needsReverification)
        self.assertFalse(self.service.list_event_reservations("e2")[0].needsReverification)
        self.assertEqual(self.service.list_event_reservations("e2")[0].reservationId, other_event)

    def test_a_flagged_reservation_still_holds_its_stock(self):
        self.reserve(quantity=3)
        self.service.flag_for_reverification("e1", "Start moved")

        availability = self.service.check_availability(
            EquipmentAvailabilityIn(equipmentId=self.equipment_id, startsAt=START, endsAt=END)
        )

        self.assertEqual(availability.availableQuantity, 2)

    def test_an_event_without_reservations_flags_nothing(self):
        self.assertEqual(self.service.flag_for_reverification("e9", "Start moved"), [])
        self.assertEqual(self.service.list_event_reservations("e9"), [])


class TestReservationReverificationRoutes(ReverificationCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()
        self.headers = {"Authorization": "Bearer token"}

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def test_coordinators_list_and_flag_an_events_reservations(self):
        held = self.reserve()
        with patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR) as caller:
            listed = self.client.get("/equipment/reservations", params={"eventId": "e1"}, headers=self.headers)
            self.assertEqual(caller.call_args.kwargs["allowed_roles"], {"techsupport", "coordinator"})
            flagged = self.client.post(
                "/equipment/reservations/reverification",
                headers=self.headers,
                json={"eventId": "e1", "reason": "Start moved"},
            )
            self.assertEqual(caller.call_args.kwargs["allowed_roles"], {"coordinator", "safety"})

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([row["reservationId"] for row in listed.json()], [held])
        self.assertEqual(flagged.status_code, 200)
        self.assertTrue(flagged.json()[0]["needsReverification"])

    def test_listing_needs_an_event_id(self):
        with patch("app.routers.equipment.resolve_caller", return_value=COORDINATOR):
            missing = self.client.get("/equipment/reservations", headers=self.headers)

        self.assertEqual(missing.status_code, 422)

    def test_a_refused_role_flags_nothing(self):
        self.reserve()
        with patch("app.routers.equipment.resolve_caller", side_effect=forbidden()):
            denied = self.client.post(
                "/equipment/reservations/reverification", headers=self.headers, json={"eventId": "e1"}
            )

        self.assertEqual(denied.status_code, 403)
        self.assertFalse(self.service.list_event_reservations("e1")[0].needsReverification)
