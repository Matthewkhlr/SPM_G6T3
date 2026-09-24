from sqlalchemy.orm import Session

from app.models.equipment_request import EquipmentRequest


class EquipmentRequestDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: str) -> EquipmentRequest | None:
        return self.db.query(EquipmentRequest).filter(EquipmentRequest.requestId == request_id).first()

    def add(self, row: EquipmentRequest) -> None:
        self.db.add(row)
