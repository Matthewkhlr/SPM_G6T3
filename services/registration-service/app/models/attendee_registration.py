from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class AttendeeRegistration(Base):
    __tablename__ = "attendee_registration"

    attendeeRegistrationId: Mapped[str] = mapped_column(String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column(String(64))
    attendeeName: Mapped[str] = mapped_column(String(255))
    attendeeEmail: Mapped[str] = mapped_column(String(255))
    userId: Mapped[str | None] = mapped_column(String(64), nullable=True)
    createdAt: Mapped[datetime] = mapped_column(DateTime)
