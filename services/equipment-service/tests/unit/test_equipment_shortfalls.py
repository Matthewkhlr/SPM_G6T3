from fastapi import HTTPException

from app.schemas.equipment import EquipmentAvailabilityIn, EquipmentCreate, EquipmentQuantityReserve, OutOfServiceCounts
from tests.unit.support import CALLER, END, START, EquipmentCase


class TestEquipmentShortfalls(EquipmentCase):
    def test_reserve_refuses_a_quantity_above_what_is_serviceable(self):
        created = self.service.create_equipment(
            EquipmentCreate(
                code="PX-200",
                name="Projector",
                category="display",
                totalQuantity=4,
                outOfService=OutOfServiceCounts(damaged=3),
            ),
            CALLER,
        )

        with self.assertRaises(HTTPException) as ctx:
            self.service.reserve_quantity(
                EquipmentQuantityReserve(
                    eventId="e1", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END
                ),
                CALLER,
            )

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(self.service._active_reservations(created.equipmentId), [])

    def test_a_shortfall_names_the_line_and_does_not_reserve(self):
        self.assertTrue(
            hasattr(self.service, "check_event_availability"),
            "check_event_availability is not implemented",
        )
        created = self.service.create_equipment(
            EquipmentCreate(code="PX-200", name="Projector", category="display", totalQuantity=4),
            CALLER,
        )
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e-other", equipmentId=created.equipmentId, quantity=3, startsAt=START, endsAt=END
            ),
            CALLER,
        )

        report = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 2}],
            START,
            END,
        )

        self.assertFalse(report["canMeet"])
        self.assertEqual(report["lines"][0]["shortfall"], 1)
        self.assertEqual(len(self.service._active_reservations(created.equipmentId)), 1)

    def test_release_returns_the_quantity_to_the_period(self):
        self.assertTrue(hasattr(self.service, "release_reservation"), "release_reservation is not implemented")
        created = self.service.create_equipment(
            EquipmentCreate(code="PX-200", name="Projector", category="display", totalQuantity=4),
            CALLER,
        )
        reserved = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END
            ),
            CALLER,
        )

        self.service.release_reservation(reserved.reservationId, CALLER)
        later = self.service.check_availability(
            EquipmentAvailabilityIn(equipmentId=created.equipmentId, startsAt=START, endsAt=END)
        )

        self.assertEqual(later.reservedQuantity, 0)
        self.assertEqual(later.availableQuantity, 4)
