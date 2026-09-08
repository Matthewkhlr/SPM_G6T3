from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EquipmentRequest(Base):
    __tablename__ = "equipment_requests"

    requestId: Mapped[str] = mapped_column("request_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64))
    equipmentId: Mapped[str] = mapped_column(
        "equipment_id", String(64), ForeignKey("equipment_info.equipment_id")
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    technicalRequirements: Mapped[str] = mapped_column("technical_requirements", Text, default="")
    requestedBy: Mapped[str] = mapped_column("requested_by", String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    startsAt: Mapped[datetime] = mapped_column("starts_at", DateTime)
    endsAt: Mapped[datetime] = mapped_column("ends_at", DateTime)
    reviewedBy: Mapped[str | None] = mapped_column("reviewed_by", String(64), nullable=True)
    reviewNote: Mapped[str] = mapped_column("review_note", Text, default="")
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    equipment: Mapped["EquipmentInfo"] = relationship("EquipmentInfo", back_populates="requests")
    reservations: Mapped[list["EquipmentReservation"]] = relationship("EquipmentReservation", back_populates="request")
