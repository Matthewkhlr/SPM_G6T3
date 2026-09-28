from sqlalchemy.orm import Session

from app.models.equipment_request import EquipmentRequest


class EquipmentRequestDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, request_id: str) -> EquipmentRequest | None:
        return self.db.query(EquipmentRequest).filter(EquipmentRequest.requestId == request_id).first()

    def add(self, row: EquipmentRequest) -> None:
        self.db.add(row)

    def list_all(self) -> list[EquipmentRequest]:
        return self.db.query(EquipmentRequest).order_by(EquipmentRequest.createdAt).all()

    def list_for_event(self, event_id: str) -> list[EquipmentRequest]:
        return (
            self.db.query(EquipmentRequest)
            .filter(EquipmentRequest.eventId == event_id)
            .order_by(EquipmentRequest.createdAt)
            .all()
        )
