from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EventSafetyReview(Base):
    """SPM-120: one submission of an event to a Safety Officer.

    `package` is the copy of the venue, equipment, and event facts taken when
    the coordinator submitted, so the officer judges exactly what was sent.
    `decision_note` holds the rejection reason or the required changes, and
    `affected` which arrangements a change request flagged for re-checking.
    A resubmission is a new row, so the history stays.
    """

    __tablename__ = "event_safety_reviews"

    reviewId: Mapped[str] = mapped_column("review_id", String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column("event_id", String(64), ForeignKey("events.event_id"), index=True)
    status: Mapped[str] = mapped_column(String(32))
    submittedBy: Mapped[str] = mapped_column("submitted_by", String(64))
    submittedAt: Mapped[datetime] = mapped_column("submitted_at", DateTime)
    crowdMovement: Mapped[str] = mapped_column("crowd_movement", Text)
    equipmentPlacement: Mapped[str] = mapped_column("equipment_placement", Text)
    package: Mapped[dict] = mapped_column(JSON)
    decidedBy: Mapped[str | None] = mapped_column("decided_by", String(64), nullable=True)
    decidedAt: Mapped[datetime | None] = mapped_column("decided_at", DateTime, nullable=True)
    decisionNote: Mapped[str | None] = mapped_column("decision_note", Text, nullable=True)
    affected: Mapped[list | None] = mapped_column(JSON, nullable=True)
