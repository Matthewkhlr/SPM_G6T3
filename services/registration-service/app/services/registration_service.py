from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.attendee_registration import AttendeeRegistration
from app.models.registration_window import RegistrationWindow
from shared.exceptions.http import conflict, not_found


def _event(event_id: str) -> dict:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{settings.event_service_url}/events/{event_id}")
    except httpx.HTTPError as exc:
        raise not_found("Event not found") from exc
    if response.status_code != 200:
        raise not_found("Event not found")
    return response.json()


def eligibility(event: dict, registered_count: int) -> tuple[bool, str | None]:
    now = datetime.utcnow()
    if event.get("status") != "confirmed":
        return False, "This event has not been confirmed yet."
    if not event.get("registrationEnabled"):
        return False, "Registration has not been enabled for this event."
    opens_raw = event.get("registrationOpensAt")
    closes_raw = event.get("registrationClosesAt")
    if not opens_raw or not closes_raw:
        return False, "Registration has not been enabled for this event."
    opens = datetime.fromisoformat(str(opens_raw).replace("Z", ""))
    closes = datetime.fromisoformat(str(closes_raw).replace("Z", ""))
    if now < opens:
        return False, f"Registration opens {opens.date()}."
    if now > closes:
        return False, "Registration has closed for this event."
    if registered_count >= event["capacity"]:
        return False, "This event has reached capacity."
    return True, None


def list_for_event(db: Session, event_id: str) -> list[AttendeeRegistration]:
    return (
        db.query(AttendeeRegistration)
        .filter(
            AttendeeRegistration.eventId == event_id,
            AttendeeRegistration.status == "registered",
        )
        .all()
    )


def register(db: Session, event_id: str, name: str, email: str, user_id: str | None) -> AttendeeRegistration:
    if not name or not email:
        raise conflict("Name and email are required.")
    event = _event(event_id)
    window = db.query(RegistrationWindow).filter(RegistrationWindow.eventId == event_id).first()
    if not window:
        raise conflict("Registration is not open for this event.")
    existing = list_for_event(db, event_id)
    ok, reason = eligibility(event, len(existing))
    if not ok:
        raise conflict(reason)
    duplicate = next((row for row in existing if row.attendeeEmail.lower() == email.lower()), None)
    if duplicate:
        raise conflict("This email is already registered for the event.")
    row = AttendeeRegistration(
        attendeeRegistrationId=str(uuid4()),
        eventId=event_id,
        attendeeName=name,
        attendeeEmail=email,
        userId=user_id,
        status="registered",
        createdAt=datetime.utcnow(),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
