from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventFieldChange(Base):
    """SPM-71 AC5: one row per edited field, with its previous and new value,
    who changed it, and when. Values are stored as text so any field type fits."""

    __tablename__ = "event_field_changes"

    changeId: Mapped[str] = mapped_column("change_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    field: Mapped[str] = mapped_column(String(64))
    oldValue: Mapped[str | None] = mapped_column("old_value", Text, nullable=True)
    newValue: Mapped[str | None] = mapped_column("new_value", Text, nullable=True)
    changedBy: Mapped[str] = mapped_column("changed_by", String(64))
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="fieldChanges")
