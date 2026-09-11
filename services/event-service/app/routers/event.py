from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.orchestration.clients import current_organiser
from app.schemas.event import EventCreate, EventOut
from app.services import event_service

router = APIRouter(prefix="/events", tags=["events"])


@router.get("", response_model=list[EventOut])
def list_events(db: Session = Depends(get_db)):
    return event_service.list_events(db)


@router.post("", response_model=EventOut, status_code=201)
def create_event(
    body: EventCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    organiser = current_organiser(authorization)
    return event_service.create_event(
        db, body, organiser["userId"], organiser.get("organisationId")
    )


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    return event_service.get_event(db, event_id)
