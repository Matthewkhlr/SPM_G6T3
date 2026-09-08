from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.equipment import EquipmentOut
from app.services import equipment_service

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentOut])
def list_equipment(db: Session = Depends(get_db)):
    return equipment_service.list_equipment(db)


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: str, db: Session = Depends(get_db)):
    return equipment_service.get_equipment(db, equipment_id)
