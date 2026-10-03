from app.models.equipment_info import EquipmentInfo
from shared.dao.base import BaseDAO


class EquipmentDAO(BaseDAO):
    def list_all(self) -> list[EquipmentInfo]:
        return self.db.query(EquipmentInfo).all()

    def get_by_id(self, equipment_id: str) -> EquipmentInfo | None:
        return self.db.query(EquipmentInfo).filter(EquipmentInfo.equipmentId == equipment_id).first()
