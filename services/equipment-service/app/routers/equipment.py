from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.equipment import (
    EquipmentOut,
    EquipmentRequestCreate,
    EquipmentRequestOut,
    EquipmentRequestReview,
    EquipmentReservationOut,
)
from app.services import equipment_service
from shared.auth.roles import resolve_caller

router = APIRouter(prefix="/equipment", tags=["equipment"])


@router.get("", response_model=list[EquipmentOut])
def list_equipment(db: Session = Depends(get_db)):
    return equipment_service.list_equipment(db)


@router.get("/{equipment_id}", response_model=EquipmentOut)
def get_equipment(equipment_id: str, db: Session = Depends(get_db)):
    return equipment_service.get_equipment(db, equipment_id)


@router.post("/requests", response_model=EquipmentRequestOut, status_code=201)
def create_request(
    body: EquipmentRequestCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return equipment_service.create_request(db, body, caller["userId"])


@router.post("/requests/{request_id}/review", response_model=EquipmentRequestOut)
def review_request(
    request_id: str,
    body: EquipmentRequestReview,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return equipment_service.review_request(db, request_id, caller["userId"], body.approve, body.reviewNote)


@router.post("/requests/{request_id}/reserve", response_model=EquipmentReservationOut, status_code=201)
def reserve_request(
    request_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return equipment_service.reserve_request(db, request_id)
