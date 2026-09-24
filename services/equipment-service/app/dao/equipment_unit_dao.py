from sqlalchemy.orm import Session

from app.models.equipment_unit import EquipmentUnit


class EquipmentUnitDAO:
    def __init__(self, db: Session):
        self.db = db

    def list_for_equipment(self, equipment_id: str) -> list[EquipmentUnit]:
        return self.db.query(EquipmentUnit).filter(EquipmentUnit.equipmentId == equipment_id).all()
