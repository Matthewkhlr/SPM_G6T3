from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, String, Text, false
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VenueBooking(Base):
    __tablename__ = "venue_bookings"
    __table_args__ = (Index("ix_venue_bookings_venue_window", "venue_id", "starts_at", "ends_at"),)

    bookingId: Mapped[str] = mapped_column("booking_id", String(64), primary_key=True)
    venueId: Mapped[str] = mapped_column("venue_id", String(64), ForeignKey("venues.venue_id"))
    eventId: Mapped[str] = mapped_column("event_id", String(64))
    requestedBy: Mapped[str] = mapped_column("requested_by", String(64))
    status: Mapped[str] = mapped_column(String(32), default="pending")
    startsAt: Mapped[datetime] = mapped_column("starts_at", DateTime)
    endsAt: Mapped[datetime] = mapped_column("ends_at", DateTime)
    setupStartsAt: Mapped[datetime] = mapped_column("setup_starts_at", DateTime)
    teardownEndsAt: Mapped[datetime] = mapped_column("teardown_ends_at", DateTime)
    requirementsSnapshot: Mapped[str] = mapped_column("requirements_snapshot", Text, default="")
    # SPM-63: the event's facts as they were when the request was sent (AC2),
    # the coordinator's own notes, and the suitability warnings the coordinator
    # acknowledged, so Venue Staff see them with the request (AC4).
    eventSnapshot: Mapped[dict | None] = mapped_column("event_snapshot", JSON, nullable=True)
    coordinatorNotes: Mapped[str | None] = mapped_column("coordinator_notes", Text, nullable=True, default="")
    warnings: Mapped[list | None] = mapped_column(JSON, nullable=True, default=list)
    # SPM-71 AC4: set when a significant event change may invalidate this
    # booking. The status is left alone so the booking keeps holding the venue.
    needsReverification: Mapped[bool] = mapped_column(
        "needs_reverification", Boolean, default=False, server_default=false()
    )
    reverificationNote: Mapped[str | None] = mapped_column("reverification_note", Text, nullable=True)
    # SPM-116: a tentative hold placed by Venue Staff on this pending request.
    # It reserves the venue until it expires or ends; see app/services/occupancy.py.
    holdExpiresAt: Mapped[datetime | None] = mapped_column("hold_expires_at", DateTime, nullable=True)
    holdPlacedBy: Mapped[str | None] = mapped_column("hold_placed_by", String(64), nullable=True)
    holdPlacedAt: Mapped[datetime | None] = mapped_column("hold_placed_at", DateTime, nullable=True)
    holdEndedAt: Mapped[datetime | None] = mapped_column("hold_ended_at", DateTime, nullable=True)
    holdEndReason: Mapped[str | None] = mapped_column("hold_end_reason", String(32), nullable=True)
    decisionReason: Mapped[str | None] = mapped_column("decision_reason", Text, nullable=True)
    reviewedBy: Mapped[str | None] = mapped_column("reviewed_by", String(64), nullable=True)
    reviewedAt: Mapped[datetime | None] = mapped_column("reviewed_at", DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    venue: Mapped["VenueInfo"] = relationship("VenueInfo", back_populates="bookings")
