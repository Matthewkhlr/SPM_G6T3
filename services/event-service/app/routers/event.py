from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.orchestration.clients import current_organiser
from app.schemas.event import EventAssignmentCreate, EventAssignmentOut, EventCreate, EventOut
from app.services import event_service
from shared.auth.roles import resolve_caller

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


@router.post("/{event_id}/assign-coordinator", response_model=EventAssignmentOut, status_code=201)
def assign_coordinator(
    event_id: str,
    body: EventAssignmentCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return event_service.assign_coordinator(db, event_id, body, caller["userId"])
