from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AttendeeRegistration(Base):
    __tablename__ = "attendee_registrations"

    attendeeRegistrationId: Mapped[str] = mapped_column(
        "attendee_registration_id", String(64), primary_key=True
    )
    eventId: Mapped[str] = mapped_column(
        "event_id", String(64), ForeignKey("registration_windows.event_id")
    )
    userId: Mapped[str | None] = mapped_column("user_id", String(64), nullable=True)
    attendeeName: Mapped[str] = mapped_column("attendee_name", String(255))
    attendeeEmail: Mapped[str] = mapped_column("attendee_email", String(255))
    status: Mapped[str] = mapped_column(String(32), default="registered")
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)
    withdrawnAt: Mapped[datetime | None] = mapped_column("withdrawn_at", DateTime, nullable=True)

    window: Mapped["RegistrationWindow"] = relationship("RegistrationWindow", back_populates="attendees")
