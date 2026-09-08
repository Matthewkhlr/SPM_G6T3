from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EventStatusHistory(Base):
    __tablename__ = "event_status_history"

    historyId: Mapped[str] = mapped_column("history_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"))
    fromStatus: Mapped[str | None] = mapped_column("from_status", String(32), nullable=True)
    toStatus: Mapped[str] = mapped_column("to_status", String(32))
    changedBy: Mapped[str] = mapped_column("changed_by", String(64))
    note: Mapped[str] = mapped_column(Text, default="")
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    event: Mapped["Event"] = relationship("Event", back_populates="statusHistory")
