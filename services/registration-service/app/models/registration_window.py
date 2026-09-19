from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class RegistrationWindow(Base):
    __tablename__ = "registration_windows"

    eventId: Mapped[str] = mapped_column("event_id", String(64), primary_key=True)
    capacity: Mapped[int] = mapped_column(Integer)
    opensAt: Mapped[datetime] = mapped_column("opens_at", DateTime)
    closesAt: Mapped[datetime] = mapped_column("closes_at", DateTime)

    attendees: Mapped[list["AttendeeRegistration"]] = relationship("AttendeeRegistration", back_populates="window")
