from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventSafetyHandoff(Base):
    """SPM-120, change 6: the arrangements on their way to a Safety Officer,
    one row per event for the current round.

    Venue Staff send the venue arrangements with the crowd-movement note, and
    technical support the technical arrangements with the equipment placement.
    Once every part the event needs is in, the row becomes a safety review and
    is removed. A part whose arrangements change before then is cleared, and a
    significant change to the event clears the row.
    """

    __tablename__ = "event_safety_handoffs"

    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"), primary_key=True)
    crowdMovement: Mapped[str | None] = mapped_column("crowd_movement", Text, nullable=True)
    venueSentBy: Mapped[str | None] = mapped_column("venue_sent_by", String(64), nullable=True)
    venueSentAt: Mapped[datetime | None] = mapped_column("venue_sent_at", DateTime, nullable=True)
    equipmentPlacement: Mapped[str | None] = mapped_column("equipment_placement", Text, nullable=True)
    technicalSentBy: Mapped[str | None] = mapped_column("technical_sent_by", String(64), nullable=True)
    technicalSentAt: Mapped[datetime | None] = mapped_column("technical_sent_at", DateTime, nullable=True)
