from sqlalchemy.orm import Session

from app.models.equipment_reservation import EquipmentReservation


class EquipmentReservationDAO:
    def __init__(self, db: Session):
        self.db = db

    def list_active_for_equipment(self, equipment_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.equipmentId == equipment_id)
            .filter(EquipmentReservation.status.in_(["active", "reserved"]))
            .all()
        )

    def get_by_request_id(self, request_id: str) -> EquipmentReservation | None:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.requestId == request_id)
            .first()
        )

    def add(self, row: EquipmentReservation) -> None:
        self.db.add(row)
