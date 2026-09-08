from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Registration(Base):
    __tablename__ = "registration"

    registrationId: Mapped[str] = mapped_column(String(64), primary_key=True)
    eventId: Mapped[str] = mapped_column(String(64), unique=True)
    capacity: Mapped[int] = mapped_column(Integer)
