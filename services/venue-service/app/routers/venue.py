from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.venue import VenueOut
from app.services import venue_service

router = APIRouter(prefix="/venues", tags=["venues"])


@router.get("", response_model=list[VenueOut])
def list_venues(db: Session = Depends(get_db)):
    return venue_service.list_venues(db)


@router.get("/{venue_id}", response_model=VenueOut)
def get_venue(venue_id: str, db: Session = Depends(get_db)):
    return venue_service.get_venue(db, venue_id)
