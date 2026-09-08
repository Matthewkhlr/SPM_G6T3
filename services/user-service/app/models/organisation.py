from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Organisation(Base):
    __tablename__ = "organisations"

    organisationId: Mapped[str] = mapped_column("organisation_id", String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    createdAt: Mapped[datetime] = mapped_column("created_at", DateTime, default=datetime.utcnow)

    users: Mapped[list["User"]] = relationship("User", back_populates="organisation")
