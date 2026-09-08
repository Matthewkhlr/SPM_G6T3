from sqlalchemy.orm import Session

from app.models.equipment_info import EquipmentInfo
from app.models.equipment_unit import EquipmentUnit
from app.schemas.equipment import EquipmentOut
from shared.exceptions.http import not_found


def _status_for(db: Session, equipment_id: str) -> str:
    units = db.query(EquipmentUnit).filter(EquipmentUnit.equipmentId == equipment_id).all()
    if not units:
        return "available"
    if any(unit.status == "maintenance" for unit in units):
        return "maintenance"
    if any(unit.status == "damaged" for unit in units):
        return "damaged"
    return "available"


def list_equipment(db: Session) -> list[EquipmentOut]:
    return [
        EquipmentOut(
            equipmentId=row.equipmentId,
            name=row.name,
            category=row.category,
            notes=row.description,
            status=_status_for(db, row.equipmentId),
        )
        for row in db.query(EquipmentInfo).all()
    ]


def get_equipment(db: Session, equipment_id: str) -> EquipmentOut:
    row = db.query(EquipmentInfo).filter(EquipmentInfo.equipmentId == equipment_id).first()
    if not row:
        raise not_found("Equipment not found")
    return EquipmentOut(
        equipmentId=row.equipmentId,
        name=row.name,
        category=row.category,
        notes=row.description,
        status=_status_for(db, equipment_id),
    )
