from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EquipmentReservation(Base):
    __tablename__ = "equipment_reservations"

    reservationId: Mapped[str] = mapped_column("reservation_id", String(64), primary_key=True)
    requestId: Mapped[str] = mapped_column(
        "request_id", String(64), ForeignKey("equipment_requests.request_id")
    )
    eventId: Mapped[str] = mapped_column("event_id", String(64))
    equipmentId: Mapped[str] = mapped_column(
        "equipment_id", String(64), ForeignKey("equipment_info.equipment_id")
    )
    quantity: Mapped[int] = mapped_column(Integer)
    startsAt: Mapped[datetime] = mapped_column("starts_at", DateTime)
    endsAt: Mapped[datetime] = mapped_column("ends_at", DateTime)
    status: Mapped[str] = mapped_column(String(32), default="active")

    request: Mapped["EquipmentRequest"] = relationship("EquipmentRequest", back_populates="reservations")
    equipment: Mapped["EquipmentInfo"] = relationship("EquipmentInfo", back_populates="reservations")
