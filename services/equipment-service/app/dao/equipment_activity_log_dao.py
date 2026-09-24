from sqlalchemy.orm import Session

from app.models.equipment_activity_log import EquipmentActivityLog


class EquipmentActivityLogDAO:
    def __init__(self, db: Session):
        self.db = db

    def add(self, row: EquipmentActivityLog) -> None:
        self.db.add(row)

    def list_for_equipment(self, equipment_id: str) -> list[EquipmentActivityLog]:
        return (
            self.db.query(EquipmentActivityLog)
            .filter(EquipmentActivityLog.equipmentId == equipment_id)
            .order_by(EquipmentActivityLog.createdAt.desc())
            .all()
        )
