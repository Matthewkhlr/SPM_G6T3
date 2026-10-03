from datetime import timedelta, timezone

from fastapi import HTTPException

from app.schemas.equipment import EquipmentAvailabilityIn, EquipmentQuantityReserve, EquipmentUpdate
from tests.unit.support import CALLER, END, START, EquipmentCase, equipment_create


class TestEquipmentReservations(EquipmentCase):
    def test_update_blocks_a_cut_that_breaks_a_reservation_until_acknowledged(self):
        created = self.service.create_equipment(equipment_create(totalQuantity=5), CALLER)
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=4, startsAt=START, endsAt=END
            ),
            CALLER,
        )

        with self.assertRaises(HTTPException) as ctx:
            self.service.update_equipment(created.equipmentId, EquipmentUpdate(totalQuantity=3), CALLER)
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("e1", ctx.exception.detail)

        acknowledged = self.service.update_equipment(
            created.equipmentId,
            EquipmentUpdate(totalQuantity=3, acknowledgeReservationImpact=True),
            CALLER,
        )
        self.assertEqual(acknowledged.totalQuantity, 3)

    def test_availability_subtracts_overlapping_reservations_only(self):
        created = self.service.create_equipment(equipment_create(), CALLER)
        aware_start = START.replace(tzinfo=timezone.utc)
        aware_end = END.replace(tzinfo=timezone.utc)
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1",
                equipmentId=created.equipmentId,
                quantity=2,
                startsAt=aware_start,
                endsAt=aware_end,
            ),
            CALLER,
        )

        overlapping = self.service.check_availability(
            EquipmentAvailabilityIn(equipmentId=created.equipmentId, startsAt=START, endsAt=END)
        )
        later = self.service.check_availability(
            EquipmentAvailabilityIn(
                equipmentId=created.equipmentId,
                startsAt=END + timedelta(days=1),
                endsAt=END + timedelta(days=1, hours=2),
            )
        )

        touching_after = self.service.check_availability(
            EquipmentAvailabilityIn(
                equipmentId=created.equipmentId,
                startsAt=END,
                endsAt=END + timedelta(hours=1),
            )
        )
        touching_before = self.service.check_availability(
            EquipmentAvailabilityIn(
                equipmentId=created.equipmentId,
                startsAt=START - timedelta(hours=1),
                endsAt=START,
            )
        )
        overlaps_by_a_second = self.service.check_availability(
            EquipmentAvailabilityIn(
                equipmentId=created.equipmentId,
                startsAt=END - timedelta(seconds=1),
                endsAt=END + timedelta(hours=1),
            )
        )

        self.assertEqual(overlapping.reservedQuantity, 2)
        self.assertEqual(overlapping.availableQuantity, 2)
        self.assertEqual(later.reservedQuantity, 0)
        self.assertEqual(later.availableQuantity, 4)
        self.assertEqual(touching_after.reservedQuantity, 0)
        self.assertEqual(touching_after.availableQuantity, 4)
        self.assertEqual(touching_before.reservedQuantity, 0)
        self.assertEqual(touching_before.availableQuantity, 4)
        self.assertEqual(overlaps_by_a_second.reservedQuantity, 2)
        self.assertEqual(overlaps_by_a_second.availableQuantity, 2)

    def test_cutting_down_to_the_reserved_quantity_is_allowed(self):
        created = self.service.create_equipment(equipment_create(code="EDGE", totalQuantity=5), CALLER)
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=4, startsAt=START, endsAt=END
            ),
            CALLER,
        )

        updated = self.service.update_equipment(created.equipmentId, EquipmentUpdate(totalQuantity=4), CALLER)

        self.assertEqual(updated.totalQuantity, 4)
        self.assertEqual(updated.serviceableQuantity, 4)

    def test_reserve_quantity_stores_an_active_hold(self):
        created = self.service.create_equipment(equipment_create(code="HOLD"), CALLER)

        reserved = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e9", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            {},
        )

        self.assertEqual(reserved.quantity, 1)
        self.assertEqual(reserved.eventId, "e9")
