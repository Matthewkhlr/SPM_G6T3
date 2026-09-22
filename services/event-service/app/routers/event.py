from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.orchestration.clients import current_organiser, current_technical_support
from app.schemas.event import (
    EventAssignmentCreate,
    EventAssignmentOut,
    EventCreate,
    EventDecision,
    EventOut,
)
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

@router.get("/upcoming/technical", response_model=list[EventOut])
def list_upcoming_events_for_technical_support(
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
    ):
    _technical_user = current_technical_support(authorization)
    return event_service.list_upcoming_events(db)

@router.get("/all", response_model=list[EventOut])
def list_all_events(db: Session = Depends(get_db)):
    return event_service.list_all_events(db)


@router.get("/confirmed", response_model=list[EventOut])
def list_confirmed_events(db: Session = Depends(get_db)):
    return event_service.list_confirmed_events(db)


@router.get("/{event_id}", response_model=EventOut)
def get_event(event_id: str, db: Session = Depends(get_db)):
    return event_service.get_event(db, event_id)


@router.post("/{event_id}/approve", response_model=EventOut)
def approve_event(
    event_id: str,
    body: EventDecision,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return event_service.approve_event(db, event_id, caller["userId"])


@router.post("/{event_id}/reject", response_model=EventOut)
def reject_event(
    event_id: str,
    body: EventDecision,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return event_service.reject_event(db, event_id, caller["userId"], body.reason or "")


@router.post("/{event_id}/assign-coordinator", response_model=EventAssignmentOut, status_code=201)
def assign_coordinator(
    event_id: str,
    body: EventAssignmentCreate,
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    caller = resolve_caller(authorization, settings.user_service_url, allowed_roles={"coordinator"})
    return event_service.assign_coordinator(db, event_id, body, caller["userId"])