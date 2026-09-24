import pytest
from fastapi import HTTPException

from app.schemas.equipment import EquipmentCreate, EquipmentUpdate, OutOfServiceCounts

CALLER = {"userId": "u-tech-1", "userName": "Tess Tech", "role": "techsupport"}


def make_equipment(**overrides):
    defaults = dict(
        code="PROJ-1",
        name="Projector PX-200",
        category="display",
        description="Includes HDMI + VGA adapters",
        totalQuantity=4,
        homeLocation="Marina Hall store",
        technicalNotes="Keep a spare lamp in the same store.",
    )
    defaults.update(overrides)
    return EquipmentCreate(**defaults)


def test_create_equipment_computes_serviceable_quantity(equipment_service):
    created = equipment_service.create_equipment(
        make_equipment(totalQuantity=10, outOfService=OutOfServiceCounts(damaged=1, maintenance=2, retired=0)),
        CALLER,
    )

    assert created.serviceableQuantity == 7
    assert created.status == "available"


def test_create_equipment_with_duplicate_code_conflicts(equipment_service):
    equipment_service.create_equipment(make_equipment(code="DUP-1"), CALLER)

    with pytest.raises(HTTPException) as exc_info:
        equipment_service.create_equipment(make_equipment(code="DUP-1", name="Other"), CALLER)

    assert exc_info.value.status_code == 409


def test_create_equipment_rejects_out_of_service_counts_above_total(equipment_service):
    with pytest.raises(HTTPException) as exc_info:
        equipment_service.create_equipment(
            make_equipment(totalQuantity=2, outOfService=OutOfServiceCounts(damaged=3)), CALLER
        )

    assert exc_info.value.status_code == 422


def test_get_equipment_missing_id_raises_404(equipment_service):
    with pytest.raises(HTTPException) as exc_info:
        equipment_service.get_equipment("does-not-exist")

    assert exc_info.value.status_code == 404


def test_update_equipment_records_a_total_quantity_change_in_the_activity_log(equipment_service):
    created = equipment_service.create_equipment(make_equipment(code="UPD-1"), CALLER)

    equipment_service.update_equipment(created.equipmentId, EquipmentUpdate(totalQuantity=8), CALLER)

    log = equipment_service.get_activity_log(created.equipmentId)
    assert log[0].action == "updated"
    assert log[0].changes["totalQuantity"] == {"old": 4, "new": 8}


def test_update_equipment_with_no_actual_changes_does_not_add_an_activity_log_entry(equipment_service):
    created = equipment_service.create_equipment(make_equipment(code="NOCHANGE-1"), CALLER)

    equipment_service.update_equipment(created.equipmentId, EquipmentUpdate(name="Projector PX-200"), CALLER)

    log = equipment_service.get_activity_log(created.equipmentId)
    assert len(log) == 1  # only the original "created" entry
    assert log[0].action == "created"
