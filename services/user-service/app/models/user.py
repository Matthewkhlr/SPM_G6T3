from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, JSON, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    userId: Mapped[str] = mapped_column("user_id", String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    userName: Mapped[str] = mapped_column("display_name", String(255))
    role: Mapped[str] = mapped_column(String(64))
    organisationId: Mapped[str | None] = mapped_column(
        "organisation_id", String(64), ForeignKey("organisations.organisation_id"), nullable=True
    )
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    communicationPreferences: Mapped[dict | None] = mapped_column(
        "communication_preferences", JSON, nullable=True
    )
    firebaseUid: Mapped[str | None] = mapped_column("firebase_uid", String(128), nullable=True)
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)
    updatedAt: Mapped[datetime] = mapped_column(
        "updated_at", DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    organisation: Mapped["Organisation | None"] = relationship("Organisation", back_populates="users")
