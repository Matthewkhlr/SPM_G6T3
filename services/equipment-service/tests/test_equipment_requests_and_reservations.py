from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.schemas.equipment import (
    EquipmentAvailabilityIn,
    EquipmentCreate,
    EquipmentQuantityReserve,
    EquipmentRequestCreate,
)

CALLER = {"userId": "u-tech-1", "userName": "Tess Tech", "role": "techsupport"}
COORDINATOR_ID = "u-coordinator-1"


def make_equipment(equipment_service, **overrides):
    defaults = dict(code="PROJ-1", name="Projector PX-200", category="display", totalQuantity=10)
    defaults.update(overrides)
    return equipment_service.create_equipment(EquipmentCreate(**defaults), CALLER)


def request_payload(equipment_id, **overrides):
    starts = datetime(2030, 1, 1, 8, 0)
    defaults = dict(
        eventId="e-1",
        equipmentId=equipment_id,
        quantity=2,
        startsAt=starts,
        endsAt=starts + timedelta(hours=8),
    )
    defaults.update(overrides)
    return EquipmentRequestCreate(**defaults)


def test_create_request_starts_pending(equipment_service):
    equipment = make_equipment(equipment_service)

    request = equipment_service.create_request(request_payload(equipment.equipmentId), COORDINATOR_ID)

    assert request.status == "pending"
    assert request.requestedBy == COORDINATOR_ID


def test_review_request_approve_then_reserve(equipment_service):
    equipment = make_equipment(equipment_service)
    request = equipment_service.create_request(request_payload(equipment.equipmentId), COORDINATOR_ID)

    reviewed = equipment_service.review_request(request.requestId, "u-tech-1", True, "Stock is free.")
    assert reviewed.status == "approved"

    reservation = equipment_service.reserve_request(request.requestId)
    assert reservation.status == "active"
    assert reservation.quantity == 2


def test_reserve_request_before_approval_conflicts(equipment_service):
    equipment = make_equipment(equipment_service)
    request = equipment_service.create_request(request_payload(equipment.equipmentId), COORDINATOR_ID)

    with pytest.raises(HTTPException) as exc_info:
        equipment_service.reserve_request(request.requestId)

    assert exc_info.value.status_code == 409


def test_reserve_request_twice_conflicts(equipment_service):
    equipment = make_equipment(equipment_service)
    request = equipment_service.create_request(request_payload(equipment.equipmentId), COORDINATOR_ID)
    equipment_service.review_request(request.requestId, "u-tech-1", True, "")
    equipment_service.reserve_request(request.requestId)

    with pytest.raises(HTTPException) as exc_info:
        equipment_service.reserve_request(request.requestId)

    assert exc_info.value.status_code == 409


def test_reviewing_an_already_decided_request_conflicts(equipment_service):
    equipment = make_equipment(equipment_service)
    request = equipment_service.create_request(request_payload(equipment.equipmentId), COORDINATOR_ID)
    equipment_service.review_request(request.requestId, "u-tech-1", False, "No stock")

    with pytest.raises(HTTPException) as exc_info:
        equipment_service.review_request(request.requestId, "u-tech-1", True, "")

    assert exc_info.value.status_code == 409


def test_check_availability_subtracts_overlapping_reservations(equipment_service):
    equipment = make_equipment(equipment_service, totalQuantity=10)
    starts = datetime(2030, 2, 1, 8, 0)
    equipment_service.reserve_quantity(
        EquipmentQuantityReserve(
            eventId="e-2", equipmentId=equipment.equipmentId, quantity=6, startsAt=starts, endsAt=starts + timedelta(hours=4)
        ),
        CALLER,
    )

    availability = equipment_service.check_availability(
        EquipmentAvailabilityIn(equipmentId=equipment.equipmentId, startsAt=starts, endsAt=starts + timedelta(hours=2))
    )

    assert availability.serviceableQuantity == 10
    assert availability.reservedQuantity == 6
    assert availability.availableQuantity == 4


def test_check_availability_ignores_non_overlapping_reservations(equipment_service):
    equipment = make_equipment(equipment_service, totalQuantity=10)
    starts = datetime(2030, 2, 1, 8, 0)
    equipment_service.reserve_quantity(
        EquipmentQuantityReserve(
            eventId="e-3", equipmentId=equipment.equipmentId, quantity=6, startsAt=starts, endsAt=starts + timedelta(hours=4)
        ),
        CALLER,
    )
    later = starts + timedelta(days=1)

    availability = equipment_service.check_availability(
        EquipmentAvailabilityIn(equipmentId=equipment.equipmentId, startsAt=later, endsAt=later + timedelta(hours=2))
    )

    assert availability.reservedQuantity == 0
    assert availability.availableQuantity == 10
