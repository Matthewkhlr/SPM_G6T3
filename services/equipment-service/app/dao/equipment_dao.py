from sqlalchemy.orm import Session

from app.models.equipment_info import EquipmentInfo


class EquipmentDAO:
    def __init__(self, db: Session):
        self.db = db

    def list_all(self) -> list[EquipmentInfo]:
        return self.db.query(EquipmentInfo).all()

    def get_by_id(self, equipment_id: str) -> EquipmentInfo | None:
        return self.db.query(EquipmentInfo).filter(EquipmentInfo.equipmentId == equipment_id).first()

    def add(self, row: EquipmentInfo) -> None:
        self.db.add(row)
