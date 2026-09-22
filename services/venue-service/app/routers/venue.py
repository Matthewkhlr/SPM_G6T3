from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.venue import (
    VenueActivityLogOut,
    VenueBookingCreate,
    VenueBookingDecision,
    VenueBookingOut,
    VenueCreate,
    VenueOut,
    VenueUpdate,
)
from app.services import venue_service
from shared.auth.deps import forwarded_bearer
from shared.auth.roles import resolve_caller
from shared.openapi import error_responses

router = APIRouter(
    prefix="/venues",
    tags=["venues"],
    responses=error_responses(401),
)

# SPM-17 AC1/AC5: only these roles can reach the catalogue at all; Event
# Organisers and Attendees are excluded, enforced here rather than only by
# hiding the tab in the frontend.
CATALOGUE_READER_ROLES = {"coordinator", "venue", "techsupport"}


@router.get(
    "",
    response_model=list[VenueOut],
    summary="List venues",
    description=(
        "Venue catalogue for coordinators, venue staff, and technical support. "
        "Retired venues are omitted unless `includeRetired` is true."
    ),
    responses=error_responses(403, 503),
)
def list_venues(
    includeRetired: bool = Query(False, description="Include retired venues in the list."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return venue_service.list_venues(db, include_retired=includeRetired)


@router.get(
    "/{venue_id}",
    response_model=VenueOut,
    summary="Get venue",
    description="Single venue, including retired ones. Coordinators, venue staff, and technical support only.",
    responses=error_responses(403, 404, 503),
)
def get_venue(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return venue_service.get_venue(db, venue_id)


@router.post(
    "",
    response_model=VenueOut,
    status_code=201,
    summary="Create venue",
    description="Venue staff only. Capacity is derived from the highest layout capacity.",
    responses=error_responses(403, 503),
)
def create_venue(
    body: VenueCreate,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.create_venue(db, body, caller)


@router.patch(
    "/{venue_id}",
    response_model=VenueOut,
    summary="Update venue",
    description="Venue staff only. Partial update; omitted fields are left unchanged.",
    responses=error_responses(403, 404, 503),
)
def update_venue(
    body: VenueUpdate,
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.update_venue(db, venue_id, body, caller)


@router.post(
    "/{venue_id}/retire",
    response_model=VenueOut,
    summary="Retire venue",
    description=(
        "Venue staff only. Soft-deletes the venue (`isActive=false`). "
        "Fails with 409 if there are confirmed upcoming bookings unless `confirm` is true."
    ),
    responses=error_responses(403, 404, 409, 503),
)
def retire_venue(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    confirm: bool = Query(
        False, description="Required if confirmed upcoming bookings would be affected."
    ),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.retire_venue(db, venue_id, caller, confirm)


@router.get(
    "/{venue_id}/activity-log",
    response_model=list[VenueActivityLogOut],
    summary="Venue activity log",
    description="Create, update, and retire history for a venue. Coordinators, venue staff, and technical support only.",
    responses=error_responses(403, 404, 503),
)
def get_venue_activity_log(
    venue_id: str = Path(..., description="Venue id, e.g. `v1`."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return venue_service.get_activity_log(db, venue_id)


@router.post(
    "/bookings",
    response_model=VenueBookingOut,
    status_code=201,
    summary="Request a venue booking",
    description="Coordinator only. Creates a booking in status `pending`. `requestedBy` is taken from the bearer token.",
    responses=error_responses(403, 503),
)
def create_booking(
    body: VenueBookingCreate,
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return venue_service.create_booking(db, body, caller["userId"])


@router.post(
    "/bookings/{booking_id}/approve",
    response_model=VenueBookingOut,
    summary="Approve a venue booking",
    description="Venue staff only. Fails with 409 if the booking is no longer `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def approve_booking(
    body: VenueBookingDecision,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.approve_booking(db, booking_id, caller["userId"], body.reason)


@router.post(
    "/bookings/{booking_id}/reject",
    response_model=VenueBookingOut,
    summary="Reject a venue booking",
    description="Venue staff only. Fails with 409 if the booking is no longer `pending`.",
    responses=error_responses(403, 404, 409, 503),
)
def reject_booking(
    body: VenueBookingDecision,
    booking_id: str = Path(..., description="Booking id returned by create booking."),
    authorization: str | None = Depends(forwarded_bearer),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.reject_booking(db, booking_id, caller["userId"], body.reason)
