from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class EquipmentUnit(Base):
    __tablename__ = "equipment_unit"

    unitId: Mapped[str] = mapped_column(String(64), primary_key=True)
    equipmentId: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(32))
