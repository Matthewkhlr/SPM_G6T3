from fastapi import APIRouter, Depends, Path
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.equipment import (
    EquipmentActivityLogOut,
    EquipmentAvailabilityIn,
    EquipmentAvailabilityOut,
    EquipmentCreate,
    EquipmentOut,
    EquipmentQuantityReserve,
    EquipmentRequestCreate,
    EquipmentRequestOut,
    EquipmentRequestReview,
    EquipmentReservationOut,
    EquipmentUpdate,
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


def _technical_support(authorization: str | None) -> dict:
    return resolve_caller(authorization, settings.user_service_url, allowed_roles={"techsupport"})


@router.post(
    "",
    response_model=EquipmentOut,
    status_code=201,
    summary="Add an equipment type",
    description="Technical support only.",
    responses=error_responses(403, 409, 422, 503),
)
def create_equipment(
    body: EquipmentCreate,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = _technical_support(authorization)
    return equipment_service.create_equipment(db, body, caller)


@router.post(
    "/availability",
    response_model=EquipmentAvailabilityOut,
    summary="Quantity available for a period",
    description="Serviceable quantity minus reservations that overlap the period.",
    responses=error_responses(404),
)
def check_availability(body: EquipmentAvailabilityIn, db: Session = Depends(get_db)):
    return equipment_service.check_availability(db, body)


@router.post(
    "/reservations",
    response_model=EquipmentReservationOut,
    status_code=201,
    summary="Reserve a quantity for a period",
    description="Technical support only. Holds quantity so availability and catalogue edits can see it.",
    responses=error_responses(403, 404, 503),
)
def reserve_quantity(
    body: EquipmentQuantityReserve,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = _technical_support(authorization)
    return equipment_service.reserve_quantity(db, body, caller)


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


@router.patch(
    "/{equipment_id}",
    response_model=EquipmentOut,
    summary="Edit an equipment type",
    description="Technical support only. Rejects out-of-service counts above the total. Returns 409 when the save cuts into reserved stock unless acknowledgeReservationImpact is true.",
    responses=error_responses(403, 404, 409, 422, 503),
)
def update_equipment(
    body: EquipmentUpdate,
    equipment_id: str = Path(..., description="Equipment id."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = _technical_support(authorization)
    return equipment_service.update_equipment(db, equipment_id, body, caller)


@router.get(
    "/{equipment_id}/activity-log",
    response_model=list[EquipmentActivityLogOut],
    summary="Catalogue activity log",
    responses=error_responses(404),
)
def get_activity_log(
    equipment_id: str = Path(..., description="Equipment id."),
    db: Session = Depends(get_db),
):
    return equipment_service.get_activity_log(db, equipment_id)


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
