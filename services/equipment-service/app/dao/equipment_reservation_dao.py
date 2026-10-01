from app.models.equipment_reservation import EquipmentReservation
from shared.dao.base import BaseDAO


class EquipmentReservationDAO(BaseDAO):
    def list_active_for_equipment(self, equipment_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.equipmentId == equipment_id)
            .filter(EquipmentReservation.status.in_(["active", "reserved"]))
            .all()
        )

    def get_by_id(self, reservation_id: str) -> EquipmentReservation | None:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.reservationId == reservation_id)
            .first()
        )

    def list_for_equipment(self, equipment_id: str) -> list[EquipmentReservation]:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.equipmentId == equipment_id)
            .all()
        )

    def get_by_request_id(self, request_id: str) -> EquipmentReservation | None:
        return (
            self.db.query(EquipmentReservation)
            .filter(EquipmentReservation.requestId == request_id)
            .first()
        )
