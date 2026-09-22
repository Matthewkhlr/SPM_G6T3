from fastapi import APIRouter, Depends, Path
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
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/equipment",
    tags=["equipment"],
    responses=error_responses(401),
)


@router.get(
    "",
    response_model=list[EquipmentOut],
    summary="List equipment",
    description="Catalogue of equipment types. `status` is derived from unit rows.",
)
def list_equipment(db: Session = Depends(get_db)):
    return equipment_service.list_equipment(db)


@router.get(
    "/{equipment_id}",
    response_model=EquipmentOut,
    summary="Get equipment",
    responses=error_responses(404),
)
def get_equipment(
    equipment_id: str = Path(..., description="Equipment id, e.g. `eq1`."),
    db: Session = Depends(get_db),
):
    return equipment_service.get_equipment(db, equipment_id)


@router.post(
    "/requests",
    response_model=EquipmentRequestOut,
    status_code=201,
    summary="Request equipment",
    description="Coordinator only. Creates a request in status `pending`. `requestedBy` is taken from the bearer token.",
    responses=error_responses(403, 503),
)
def create_request(
    body: EquipmentRequestCreate,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return equipment_service.create_request(db, body, caller["userId"])


@router.post(
    "/requests/{request_id}/review",
    response_model=EquipmentRequestOut,
    summary="Review an equipment request",
    description="Technical support only. Sets status to `approved` or `rejected`. Fails with 409 if the request is no longer `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def review_request(
    body: EquipmentRequestReview,
    request_id: str = Path(..., description="Request id returned by create request."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return equipment_service.review_request(db, request_id, caller["userId"], body.approve, body.reviewNote)


@router.post(
    "/requests/{request_id}/reserve",
    response_model=EquipmentReservationOut,
    status_code=201,
    summary="Reserve approved equipment",
    description="Technical support only. Request must already be `approved`. Fails with 409 otherwise.",
    responses=error_responses(403, 404, 409, 503),
)
def reserve_request(
    request_id: str = Path(..., description="Request id returned by create request."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})
    return equipment_service.reserve_request(db, request_id)
