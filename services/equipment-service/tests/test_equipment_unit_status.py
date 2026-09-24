from app.models.equipment_unit import EquipmentUnit
from app.schemas.equipment import EquipmentCreate

CALLER = {"userId": "u-tech-1", "userName": "Tess Tech", "role": "techsupport"}


def make_equipment(equipment_service, **overrides):
    defaults = dict(code="UNIT-1", name="Projector PX-200", category="display", totalQuantity=4)
    defaults.update(overrides)
    return equipment_service.create_equipment(EquipmentCreate(**defaults), CALLER)


def add_unit(db_session, equipment_id, unit_id, status):
    unit = EquipmentUnit(unitId=unit_id, equipmentId=equipment_id, status=status)
    db_session.add(unit)
    db_session.commit()
    return unit


def test_status_is_available_when_equipment_has_no_unit_rows(equipment_service):
    equipment = make_equipment(equipment_service, code="UNIT-A")

    assert equipment.status == "available"


def test_status_is_available_when_all_units_are_available(equipment_service, db_session):
    equipment = make_equipment(equipment_service, code="UNIT-B")
    add_unit(db_session, equipment.equipmentId, "unit-1", "available")
    add_unit(db_session, equipment.equipmentId, "unit-2", "available")

    fetched = equipment_service.get_equipment(equipment.equipmentId)

    assert fetched.status == "available"


def test_status_is_maintenance_when_any_unit_is_in_maintenance(equipment_service, db_session):
    equipment = make_equipment(equipment_service, code="UNIT-C")
    add_unit(db_session, equipment.equipmentId, "unit-1", "available")
    add_unit(db_session, equipment.equipmentId, "unit-2", "maintenance")

    fetched = equipment_service.get_equipment(equipment.equipmentId)

    assert fetched.status == "maintenance"


def test_status_is_damaged_when_any_unit_is_damaged_and_none_are_in_maintenance(equipment_service, db_session):
    equipment = make_equipment(equipment_service, code="UNIT-D")
    add_unit(db_session, equipment.equipmentId, "unit-1", "available")
    add_unit(db_session, equipment.equipmentId, "unit-2", "damaged")

    fetched = equipment_service.get_equipment(equipment.equipmentId)

    assert fetched.status == "damaged"


def test_maintenance_takes_priority_over_damaged(equipment_service, db_session):
    equipment = make_equipment(equipment_service, code="UNIT-E")
    add_unit(db_session, equipment.equipmentId, "unit-1", "damaged")
    add_unit(db_session, equipment.equipmentId, "unit-2", "maintenance")

    fetched = equipment_service.get_equipment(equipment.equipmentId)

    assert fetched.status == "maintenance"
