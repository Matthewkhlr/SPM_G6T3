from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.models.attendee_registration import AttendeeRegistration
from shared.exceptions.http import conflict, not_found


def _event(event_id: str, authorization: str | None) -> dict:
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.event_service_url}/events/{event_id}",
                headers={"Authorization": authorization} if authorization else {},
            )
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


class RegistrationService:
    def __init__(
        self,
        db: Session,
        registration_dao: AttendeeRegistrationDAO,
        window_dao: RegistrationWindowDAO,
    ):
        self.db = db
        self.registration_dao = registration_dao
        self.window_dao = window_dao

    def list_for_event(self, event_id: str) -> list[AttendeeRegistration]:
        return self.registration_dao.list_for_event(event_id)

    def register(
        self, event_id: str, name: str, email: str, user_id: str | None, authorization: str | None = None
    ) -> AttendeeRegistration:
        if not name or not email:
            raise conflict("Name and email are required.")
        event = _event(event_id, authorization)
        window = self.window_dao.get_for_event(event_id)
        if not window:
            raise conflict("Registration is not open for this event.")
        existing = self.list_for_event(event_id)
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
        self.registration_dao.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
