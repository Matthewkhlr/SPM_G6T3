from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    userId: Mapped[str] = mapped_column(String(64), primary_key=True)
    userName: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    role: Mapped[str] = mapped_column(String(64))
    password: Mapped[str] = mapped_column(String(255))
