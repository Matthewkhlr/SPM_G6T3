from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventChangeRequest(Base):
    __tablename__ = "event_change_requests"

    changeRequestId: Mapped[str] = mapped_column("change_request_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    requestedBy: Mapped[str] = mapped_column("requested_by", String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    summary: Mapped[str] = mapped_column(Text, default="")
    proposedChanges: Mapped[dict | None] = mapped_column("proposed_changes", JSON, nullable=True)
    affectsVenue: Mapped[bool] = mapped_column("affects_venue", Boolean, default=False)
    affectsEquipment: Mapped[bool] = mapped_column("affects_equipment", Boolean, default=False)
    affectsRegistration: Mapped[bool] = mapped_column("affects_registration", Boolean, default=False)
    reviewedBy: Mapped[str | None] = mapped_column("reviewed_by", String(64), nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column("reviewed_at", DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="changeRequests")
