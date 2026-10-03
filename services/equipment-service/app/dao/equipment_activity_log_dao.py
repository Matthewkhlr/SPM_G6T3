from app.models.equipment_activity_log import EquipmentActivityLog
from shared.dao.base import BaseDAO


class EquipmentActivityLogDAO(BaseDAO):
    def list_for_equipment(self, equipment_id: str) -> list[EquipmentActivityLog]:
        return (
            self.db.query(EquipmentActivityLog)
            .filter(EquipmentActivityLog.equipmentId == equipment_id)
            .order_by(EquipmentActivityLog.createdAt.desc())
            .all()
        )
