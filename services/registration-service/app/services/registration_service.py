import logging
from datetime import datetime
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.dao.attendee_registration_dao import AttendeeRegistrationDAO
from app.dao.registration_window_dao import RegistrationWindowDAO
from app.models.attendee_registration import AttendeeRegistration
from shared.exceptions.http import conflict, forbidden, not_found, unauthorized
from shared.services.base import BaseService

logger = logging.getLogger(__name__)

_CLOSED_EVENT_STATUSES = {"completed", "cancelled"}


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


def _registration_access(event_id: str, authorization: str | None) -> dict:
    """Ask event-service whether this caller may see the registration list."""
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.event_service_url}/events/{event_id}/registration-access",
                headers={"Authorization": authorization} if authorization else {},
            )
    except httpx.HTTPError as exc:
        raise not_found("Event not found") from exc
    if response.status_code == 403:
        raise forbidden("You do not have permission to view these registrations.")
    if response.status_code == 401:
        raise unauthorized("Invalid or expired token")
    if response.status_code != 200:
        raise not_found("Event not found")
    return response.json()


def _remaining(capacity: int, registered: int) -> int:
    remaining = capacity - registered
    if remaining < 0:
        remaining = 0
    return remaining


def _owns(row: AttendeeRegistration, caller: dict) -> bool:
    user_id = caller.get("userId") or ""
    email = (caller.get("email") or "").lower()
    if user_id and row.userId and user_id == row.userId:
        return True
    if email and row.attendeeEmail and email == row.attendeeEmail.lower():
        return True
    return False


def withdrawal_unavailable(event: dict) -> str | None:
    """Why this event cannot be withdrawn from, or None when withdrawal is open.

    The start instant itself is closed: an event has started at
    `proposedStartAt`, so withdrawal is only open while now is strictly earlier.
    Completed and cancelled events are closed even when that start is still ahead.
    """
    now = datetime.utcnow()
    status = str(event.get("status") or "").lower()
    if status in _CLOSED_EVENT_STATUSES:
        return "Withdrawal is unavailable because this event has been completed or cancelled."
    start_raw = event.get("proposedStartAt")
    if not start_raw:
        return "Withdrawal is unavailable because this event has no start time."
    start = datetime.fromisoformat(str(start_raw).replace("Z", ""))
    if now >= start:
        return "Withdrawal is unavailable because this event has already started."
    return None


def _notify_withdrawal(row: AttendeeRegistration, event: dict, authorization: str | None) -> None:
    """Tell the attendee they withdrew. A notification failure does not undo the withdrawal."""
    event_name = event.get("eventName") or row.eventId
    title = "Registration withdrawn"
    body = f"You have withdrawn from {event_name} ({row.eventId}). Your place has been released."
    headers = {"Authorization": authorization} if authorization else {}
    try:
        with httpx.Client(timeout=5.0) as client:
            client.post(
                f"{settings.notification_service_url}/notifications/records",
                json={
                    "eventId": row.eventId,
                    "type": "registration.withdrawn",
                    "title": title,
                    "body": body,
                },
                headers=headers,
            )
            client.post(
                f"{settings.notification_service_url}/notifications",
                json={"to": row.attendeeEmail, "subject": title, "body": body},
                headers=headers,
            )
    except httpx.HTTPError:
        logger.warning("withdrawal notification failed for %s", row.attendeeRegistrationId)


class RegistrationService(BaseService):
    def __init__(
        self,
        db: Session,
        registration_dao: AttendeeRegistrationDAO,
        window_dao: RegistrationWindowDAO,
    ):
        super().__init__(db)
        self.registration_dao = registration_dao
        self.window_dao = window_dao

    def list_for_event(self, event_id: str) -> list[AttendeeRegistration]:
        return self.registration_dao.list_for_event(event_id)

    def registered_count(self, event_id: str) -> int:
        return len(self.list_for_event(event_id))

    def registration_roster(
        self, event_id: str, authorization: str | None, include_withdrawn: bool = True
    ) -> dict:
        access = _registration_access(event_id, authorization)
        if not access.get("registrationEnabled"):
            raise not_found("Registration has not been enabled for this event.")
        rows = self.registration_dao.list_all_for_event(event_id)
        registered = [row for row in rows if row.status == "registered"]
        withdrawn = [row for row in rows if row.status == "withdrawn"]
        capacity = int(access.get("capacity") or 0)
        remaining = _remaining(capacity, len(registered))
        visible = rows if include_withdrawn else registered
        return {
            "eventId": event_id,
            "capacity": capacity,
            "registered": len(registered),
            "withdrawn": len(withdrawn),
            "remaining": remaining,
            "remainingPlaces": remaining,
            "placesRemaining": remaining,
            "registrationOpensAt": access.get("registrationOpensAt"),
            "registrationClosesAt": access.get("registrationClosesAt"),
            "attendees": visible,
        }

    def registration_summary(self, event_id: str, authorization: str | None = None) -> dict:
        event = _event(event_id, authorization)
        return self._summary(event_id, int(event.get("capacity") or 0))

    def attendee_places(self, event_id: str, authorization: str | None) -> dict:
        """Places left for an attendee. Names of other attendees are not included."""
        event = _event(event_id, authorization)
        if not event.get("registrationEnabled"):
            raise not_found("Registration has not been enabled for this event.")
        summary = self._summary(event_id, int(event.get("capacity") or 0))
        summary["registrationOpensAt"] = event.get("registrationOpensAt")
        summary["registrationClosesAt"] = event.get("registrationClosesAt")
        summary["attendees"] = []
        return summary

    def _summary(self, event_id: str, capacity: int) -> dict:
        rows = self.registration_dao.list_all_for_event(event_id)
        registered = [row for row in rows if row.status == "registered"]
        withdrawn = [row for row in rows if row.status == "withdrawn"]
        remaining = _remaining(capacity, len(registered))
        return {
            "eventId": event_id,
            "capacity": capacity,
            "registered": len(registered),
            "withdrawn": len(withdrawn),
            "remaining": remaining,
            "remainingPlaces": remaining,
            "placesRemaining": remaining,
        }

    def list_registrations(self, event_id: str, include_withdrawn: bool = True) -> list[AttendeeRegistration]:
        rows = self.registration_dao.list_all_for_event(event_id)
        if not include_withdrawn:
            return [row for row in rows if row.status == "registered"]
        return rows

    def list_for_attendee(self, email: str) -> list[AttendeeRegistration]:
        return self.registration_dao.list_for_email(email)

    def list_owned(self, user_id: str | None, email: str | None) -> list[AttendeeRegistration]:
        return self.registration_dao.list_owned(user_id, email)

    def get_for_caller(self, registration_id: str, caller: dict) -> AttendeeRegistration:
        return self._owned_row(registration_id, caller)

    def withdraw(self, event_id: str, email: str, authorization: str | None = None) -> AttendeeRegistration:
        current = self.registration_dao.find_for_event_email(event_id, email, status="registered")
        if current is None:
            previous = self.registration_dao.find_for_event_email(event_id, email)
            if previous is not None:
                raise conflict("You are not currently registered for this event.")
            raise not_found("Registration not found")
        return self._withdraw_row(current, authorization)

    def withdraw_for_caller(
        self, registration_id: str, caller: dict, authorization: str | None = None
    ) -> AttendeeRegistration:
        row = self._owned_row(registration_id, caller)
        if row.status != "registered":
            raise conflict("You are not currently registered for this event.")
        return self._withdraw_row(row, authorization)

    def _owned_row(self, registration_id: str, caller: dict) -> AttendeeRegistration:
        row = self._require(self.registration_dao.get(registration_id), "Registration not found")
        if not _owns(row, caller):
            raise forbidden("You do not have permission to use this registration.")
        return row

    def _withdraw_row(self, row: AttendeeRegistration, authorization: str | None) -> AttendeeRegistration:
        event = _event(row.eventId, authorization)
        reason = withdrawal_unavailable(event)
        if reason:
            raise conflict(reason)
        row.status = "withdrawn"
        row.withdrawnAt = datetime.utcnow()
        self.db.commit()
        self.db.refresh(row)
        _notify_withdrawal(row, event, authorization)
        return row

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
