from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Event(Base):
    __tablename__ = "events"

    eventId: Mapped[str] = mapped_column("event_id", String(64), primary_key=True)
    organiserId: Mapped[str] = mapped_column("organiser_id", String(64))
    organisationId: Mapped[str | None] = mapped_column("organisation_id", String(64), nullable=True)
    coordinatorId: Mapped[str | None] = mapped_column("coordinator_id", String(64), nullable=True)
    eventName: Mapped[str] = mapped_column("name", String(255))
    purpose: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    proposedStartAt: Mapped[datetime | None] = mapped_column("proposed_start_at", DateTime, nullable=True)
    proposedEndAt: Mapped[datetime | None] = mapped_column("proposed_end_at", DateTime, nullable=True)
    expectedAttendance: Mapped[int] = mapped_column("expected_attendance", Integer, default=0)
    venueRequirements: Mapped[str] = mapped_column("venue_requirements", Text, default="")
    accessibilityNeeds: Mapped[str] = mapped_column("accessibility_needs", Text, default="")
    equipmentRequirements: Mapped[str] = mapped_column("equipment_requirements", Text, default="")
    layoutPreference: Mapped[str | None] = mapped_column("layout_preference", String(64), nullable=True)
    registrationEnabled: Mapped[bool] = mapped_column("registration_enabled", Boolean, default=False)
    registrationOpensAt: Mapped[datetime | None] = mapped_column(
        "registration_opens_at", DateTime, nullable=True
    )
    registrationClosesAt: Mapped[datetime | None] = mapped_column(
        "registration_closes_at", DateTime, nullable=True
    )
    capacity: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32))
    submittedAt: Mapped[datetime | None] = mapped_column("submitted_at", DateTime, nullable=True)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        "updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    reviews: Mapped[list["EventReview"]] = relationship("EventReview", back_populates="event")
    assignments: Mapped[list["EventAssignment"]] = relationship("EventAssignment", back_populates="event")
    changeRequests: Mapped[list["EventChangeRequest"]] = relationship("EventChangeRequest", back_populates="event")
    statusHistory: Mapped[list["EventStatusHistory"]] = relationship("EventStatusHistory", back_populates="event")
