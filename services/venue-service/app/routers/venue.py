from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.venue import VenueBookingCreate, VenueBookingDecision, VenueBookingOut, VenueOut
from app.services import venue_service
from shared.auth.roles import resolve_caller

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueOut])
def list_venues(db: Session = Depends(get_db)):
    return venue_service.list_venues(db)


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(venue_id: str, db: Session = Depends(get_db)):
    return venue_service.get_venue(db, venue_id)


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
