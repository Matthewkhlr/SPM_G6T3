from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class VenueUnavailability(Base):
    __tablename__ = "venue_unavailability"

    unavailabilityId: Mapped[str] = mapped_column("unavailability_id", String(64), primary_key=True)
    venueId: Mapped[str] = mapped_column("venue_id", String(64), ForeignKey("venues.venue_id"))
    startsAt: Mapped[datetime] = mapped_column("starts_at", DateTime)
    endsAt: Mapped[datetime] = mapped_column("ends_at", DateTime)
    reason: Mapped[str] = mapped_column(Text, default="")
    createdBy: Mapped[str] = mapped_column("created_by", String(64))
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    venue: Mapped["VenueInfo"] = relationship("VenueInfo", back_populates="unavailability")
