from app.models.equipment_unit import EquipmentUnit
from shared.dao.base import BaseDAO


class EquipmentUnitDAO(BaseDAO):
    def list_for_equipment(self, equipment_id: str) -> list[EquipmentUnit]:
        return self.db.query(EquipmentUnit).filter(EquipmentUnit.equipmentId == equipment_id).all()
