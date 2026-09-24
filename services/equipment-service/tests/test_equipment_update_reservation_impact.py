from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.schemas.equipment import EquipmentCreate, EquipmentQuantityReserve, EquipmentUpdate, OutOfServiceCounts

CALLER = {"userId": "u-tech-1", "userName": "Tess Tech", "role": "techsupport"}


def test_update_that_cuts_below_a_reserved_quantity_is_blocked_unless_acknowledged(equipment_service):
    created = equipment_service.create_equipment(
        EquipmentCreate(code="PROJ-2", name="Projector PX-200", category="display", totalQuantity=10), CALLER
    )
    starts = datetime(2030, 3, 1, 8, 0)
    equipment_service.reserve_quantity(
        EquipmentQuantityReserve(
            eventId="e-blocked", equipmentId=created.equipmentId, quantity=8, startsAt=starts, endsAt=starts + timedelta(hours=4)
        ),
        CALLER,
    )

    # Dropping out-of-service counts so serviceable falls to 3, below the 8 reserved for e-blocked.
    with pytest.raises(HTTPException) as exc_info:
        equipment_service.update_equipment(
            created.equipmentId,
            EquipmentUpdate(outOfService=OutOfServiceCounts(damaged=7)),
            CALLER,
        )

    assert exc_info.value.status_code == 409
    assert "e-blocked" in exc_info.value.detail

    # And it genuinely didn't apply the change.
    unchanged = equipment_service.get_equipment(created.equipmentId)
    assert unchanged.serviceableQuantity == 10


def test_update_that_cuts_below_a_reserved_quantity_succeeds_when_acknowledged(equipment_service):
    created = equipment_service.create_equipment(
        EquipmentCreate(code="PROJ-3", name="Projector PX-200", category="display", totalQuantity=10), CALLER
    )
    starts = datetime(2030, 3, 1, 8, 0)
    equipment_service.reserve_quantity(
        EquipmentQuantityReserve(
            eventId="e-ack", equipmentId=created.equipmentId, quantity=8, startsAt=starts, endsAt=starts + timedelta(hours=4)
        ),
        CALLER,
    )

    updated = equipment_service.update_equipment(
        created.equipmentId,
        EquipmentUpdate(outOfService=OutOfServiceCounts(damaged=7), acknowledgeReservationImpact=True),
        CALLER,
    )

    assert updated.serviceableQuantity == 3
