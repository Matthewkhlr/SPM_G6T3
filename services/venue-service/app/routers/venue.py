from fastapi import APIRouter, Depends, Header
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
from shared.auth.roles import resolve_caller

router = APIRouter(prefix="/venues", tags=["venues"])

# SPM-17 AC1/AC5: only these roles can reach the catalogue at all; Event
# Organisers and Attendees are excluded, enforced here rather than only by
# hiding the tab in the frontend.
CATALOGUE_READER_ROLES = {"coordinator", "venue", "techsupport"}


@router.get("", response_model=list[VenueOut])
def list_venues(
    includeRetired: bool = False,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return venue_service.list_venues(db, include_retired=includeRetired)


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(
    venue_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return venue_service.get_venue(db, venue_id)


@router.post("", response_model=VenueOut, status_code=201)
def create_venue(
    body: VenueCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.create_venue(db, body, caller)


@router.patch("/{venue_id}", response_model=VenueOut)
def update_venue(
    venue_id: str,
    body: VenueUpdate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.update_venue(db, venue_id, body, caller)


@router.post("/{venue_id}/retire", response_model=VenueOut)
def retire_venue(
    venue_id: str,
    confirm: bool = False,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.retire_venue(db, venue_id, caller, confirm)


@router.get("/{venue_id}/activity-log", response_model=list[VenueActivityLogOut])
def get_venue_activity_log(
    venue_id: str,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    resolve_caller(authorization, settings.user_service_url, allowed_roles=CATALOGUE_READER_ROLES)
    return venue_service.get_activity_log(db, venue_id)


@router.post("/bookings", response_model=VenueBookingOut, status_code=201)
def create_booking(
    body: VenueBookingCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return venue_service.create_booking(db, body, caller["userId"])


@router.post("/bookings/{booking_id}/approve", response_model=VenueBookingOut)
def approve_booking(
    booking_id: str,
    body: VenueBookingDecision,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.approve_booking(db, booking_id, caller["userId"], body.reason)


@router.post("/bookings/{booking_id}/reject", response_model=VenueBookingOut)
def reject_booking(
    booking_id: str,
    body: VenueBookingDecision,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"venue"})
    return venue_service.reject_booking(db, booking_id, caller["userId"], body.reason)
