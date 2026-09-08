from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventAssignment(Base):
    __tablename__ = "event_assignments"

    assignmentId: Mapped[str] = mapped_column("assignment_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    coordinatorId: Mapped[str] = mapped_column("coordinator_id", String(64))
    assignedBy: Mapped[str] = mapped_column("assigned_by", String(64))
    assignedAt: Mapped[datetime] = mapped_column("assigned_at", DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="assignments")
