from app.models.equipment_request import EquipmentRequest
from shared.dao.base import BaseDAO


class EquipmentRequestDAO(BaseDAO):
    def get_by_id(self, request_id: str) -> EquipmentRequest | None:
        return self.db.query(EquipmentRequest).filter(EquipmentRequest.requestId == request_id).first()

    def list_all(self) -> list[EquipmentRequest]:
        return self.db.query(EquipmentRequest).order_by(EquipmentRequest.createdAt).all()

    def list_for_event(self, event_id: str) -> list[EquipmentRequest]:
        return (
            self.db.query(EquipmentRequest)
            .filter(EquipmentRequest.eventId == event_id)
            .order_by(EquipmentRequest.createdAt)
            .all()
        )
