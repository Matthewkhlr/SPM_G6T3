from datetime import timedelta

from fastapi import HTTPException

from app.schemas.equipment import (
    EquipmentAvailabilityIn,
    EquipmentCreate,
    EquipmentQuantityReserve,
    EquipmentRequestCreate,
    OutOfServiceCounts,
)
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

        held = self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e1", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        self.assertEqual(held.quantity, 1)

    def test_a_shortfall_names_the_line_and_does_not_reserve(self):
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
        before = len(self.service._active_reservations(created.equipmentId))

        report = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 2}],
            START,
            END,
        )
        again = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 2}],
            START,
            END,
        )

        self.assertFalse(report["canMeet"])
        self.assertEqual(report["lines"][0]["shortfall"], 1)
        self.assertEqual(report["lines"][0]["name"], "Projector")
        self.assertEqual(report["lines"][0]["conflictingEvents"][0]["eventId"], "e-other")
        self.assertEqual(again, report)
        self.assertEqual(len(self.service._active_reservations(created.equipmentId)), before)

    def test_exact_fit_and_a_shortfall_of_one(self):
        created = self.service.create_equipment(
            EquipmentCreate(code="EXACT", name="Clicker", category="display", totalQuantity=3),
            CALLER,
        )

        exact = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 3}],
            START,
            END,
        )
        short = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 4}],
            START,
            END,
        )
        fewer = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 2}],
            START,
            END,
        )

        self.assertTrue(exact["canMeet"])
        self.assertEqual(exact["lines"][0]["availableQuantity"], 3)
        self.assertEqual(exact["lines"][0]["shortfall"], 0)
        self.assertEqual(short["lines"][0]["shortfall"], 1)
        self.assertFalse(short["canMeet"])
        self.assertEqual(fewer["lines"][0]["shortfall"], 0)
        self.assertEqual(fewer["lines"][0]["availableQuantity"], 3)

    def test_out_of_service_stock_is_excluded(self):
        created = self.service.create_equipment(
            EquipmentCreate(
                code="OOS",
                name="Mic",
                category="audio",
                totalQuantity=6,
                outOfService=OutOfServiceCounts(damaged=1, maintenance=1, retired=1),
            ),
            CALLER,
        )

        report = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 2}],
            START,
            END,
        )

        self.assertEqual(report["lines"][0]["availableQuantity"], 3)
        self.assertTrue(report["canMeet"])

    def test_touching_periods_do_not_compete_and_one_second_does(self):
        created = self.service.create_equipment(
            EquipmentCreate(code="TOUCH", name="Screen", category="display", totalQuantity=4),
            CALLER,
        )
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e-touch",
                equipmentId=created.equipmentId,
                quantity=4,
                startsAt=END,
                endsAt=END + timedelta(hours=1),
            ),
            CALLER,
        )

        touching = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 4}],
            START,
            END,
        )
        overlap = self.service.check_event_availability(
            [{"equipmentId": created.equipmentId, "quantity": 4}],
            END - timedelta(seconds=1),
            END + timedelta(hours=1),
        )

        self.assertEqual(touching["lines"][0]["availableQuantity"], 4)
        self.assertEqual(touching["lines"][0]["conflictingEvents"], [])
        self.assertEqual(overlap["lines"][0]["availableQuantity"], 0)
        self.assertEqual(overlap["lines"][0]["conflictingEvents"][0]["eventId"], "e-touch")

    def test_an_events_own_reservation_does_not_reduce_its_check(self):
        created = self.service.create_equipment(
            EquipmentCreate(code="OWN", name="Lamp", category="lighting", totalQuantity=4),
            CALLER,
        )
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e-self", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        self.service.reserve_quantity(
            EquipmentQuantityReserve(
                eventId="e-other", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END
            ),
            CALLER,
        )
        self.service.create_request(
            EquipmentRequestCreate(eventId="e-self", equipmentId=created.equipmentId, quantity=2, startsAt=START, endsAt=END),
            "u-coord",
        )

        report = self.service.check_event_request("e-self")

        self.assertEqual(report["lines"][0]["availableQuantity"], 3)
        self.assertEqual(report["lines"][0]["conflictingEvents"], [{"eventId": "e-other", "quantity": 1}])
        self.assertTrue(report["canMeet"])

    def test_a_rejected_request_is_omitted_and_a_short_event_is_named(self):
        created = self.service.create_equipment(
            EquipmentCreate(code="REJ", name="Cable", category="video", totalQuantity=2),
            CALLER,
        )
        rejected = self.service.create_request(
            EquipmentRequestCreate(eventId="e-rej", equipmentId=created.equipmentId, quantity=1, startsAt=START, endsAt=END),
            "u-coord",
        )
        self.service.review_request(rejected.requestId, "u-tech", False, "no")
        self.service.create_request(
            EquipmentRequestCreate(eventId="e-short", equipmentId=created.equipmentId, quantity=3, startsAt=START, endsAt=END),
            "u-coord",
        )

        self.assertEqual(self.service.check_event_request("e-rej"), {"canMeet": True, "canBeMet": True, "lines": []})
        self.assertEqual(self.service.check_event_request("e-missing"), {"canMeet": True, "canBeMet": True, "lines": []})
        short = self.service.check_event_request("e-short")
        self.assertFalse(short["canMeet"])
        self.assertEqual(short["lines"][0]["shortfall"], 1)
        self.assertEqual(short["lines"][0]["name"], "Cable")

    def test_release_returns_the_quantity_to_the_period(self):
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

        with self.assertRaises(HTTPException) as missing:
            self.service.release_reservation("missing", CALLER)
        self.assertEqual(missing.exception.status_code, 404)

        with self.assertRaises(HTTPException) as again:
            self.service.release_reservation(reserved.reservationId, CALLER)
        self.assertEqual(again.exception.status_code, 409)
