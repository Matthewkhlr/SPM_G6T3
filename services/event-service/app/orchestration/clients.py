import logging
import time
from datetime import datetime

import httpx

from app.core.config import settings
from shared.exceptions.http import forbidden, service_unavailable, unauthorized

logger = logging.getLogger("perf.clients")

# Reused across calls so we're not paying a fresh TCP connect/teardown on
# every registration_count() call.
_registration_client = httpx.Client(timeout=3.0)

# Reused for organisation_names() the same way.
_user_directory_client = httpx.Client(timeout=3.0)


def registration_count(event_id: str, authorization: str | None = None) -> int:
    start = time.perf_counter()
    headers = {"Authorization": authorization} if authorization else {}
    try:
        response = _registration_client.get(
            f"{settings.registration_service_url}/registrations/count",
            params={"eventId": event_id},
            headers=headers,
        )
        if response.status_code == 200:
            return int(response.json().get("count", 0))
        logger.info(
            "registration_count(%s) got status %s", event_id, response.status_code
        )
    except httpx.HTTPError as exc:
        logger.info("registration_count(%s) raised %r", event_id, exc)
        return 0
    finally:
        logger.info(
            "registration_count(%s) took %.3fs", event_id, time.perf_counter() - start
        )
    return 0


def organisation_names(authorization: str | None = None) -> dict[str, str]:
    """organisationId -> name, for display (e.g. the coordinator review queue).

    Fetched ONCE per caller (see _to_out_list in event_service.py) rather than
    once per event, for the same reason registration_count() was moved off a
    fresh-client-per-call pattern: a per-row network call here would
    reintroduce the same N-calls-per-list lag that registration_count used to
    cause. Best-effort - an empty dict just means organisationName comes back
    null on every row, not a broken response.
    """
    headers = {"Authorization": authorization} if authorization else {}
    try:
        response = _user_directory_client.get(
            f"{settings.user_service_url}/organisations",
            headers=headers,
        )
    except httpx.HTTPError as exc:
        logger.info("organisation_names raised %r", exc)
        return {}
    if response.status_code != 200:
        logger.info("organisation_names got status %s", response.status_code)
        return {}
    return {row["organisationId"]: row["name"] for row in response.json()}


def current_organiser(authorization: str | None) -> dict:
    """Resolve the caller's bearer token to their ConnectSphere user record.

    A Firebase token only carries uid/email — role and organisation live in
    user-service's database, which this service cannot read directly. So the
    token is forwarded to user-service's /users/me, which re-verifies it and
    maps it to the local user via firebase_uid.
    """
    if not authorization:
        raise unauthorized()
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.user_service_url}/users/me",
                headers={"Authorization": authorization},
            )
    except httpx.HTTPError as exc:
        raise unauthorized("Could not verify identity") from exc
    if response.status_code != 200:
        raise unauthorized("Could not verify identity")
    user = response.json()
    if user.get("role") != "organiser":
        raise forbidden("Only event organisers can create events")
    return user

def current_technical_support(authorization: str | None) -> dict:
    if not authorization:
        raise unauthorized()

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(
                f"{settings.user_service_url}/users/me",
                headers={"Authorization": authorization},
            )
    except httpx.HTTPError as exc:
        raise unauthorized("Could not verify identity") from exc

    if response.status_code != 200:
        raise unauthorized("Could not verify identity")

    user = response.json()
    if user.get("role") != "techsupport":
        raise forbidden("Only technical support staff can view upcoming events")

    return user

# SPM-71: a significant edit must never quietly invalidate an arrangement, so
# when venue-service or equipment-service cannot be reached the edit is
# refused (503) instead of being saved without the arrangements checked.
ARRANGEMENTS_UNREACHABLE = (
    "Venue bookings and equipment reservations could not be checked right now, "
    "so the change was not saved. Please try again shortly."
)
# Equipment reservation statuses that still hold stock for the event.
HOLDING_RESERVATION_STATUSES = ("active", "reserved")


def _arrangement_rows(method: str, url: str, authorization: str | None, **kwargs) -> list[dict]:
    headers = {"Authorization": authorization} if authorization else {}
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        logger.info("%s %s raised %r", method, url, exc)
        raise service_unavailable(ARRANGEMENTS_UNREACHABLE) from exc
    if response.status_code != 200:
        logger.info("%s %s got status %s", method, url, response.status_code)
        raise service_unavailable(ARRANGEMENTS_UNREACHABLE)
    return response.json()


def _venue_arrangement(row: dict) -> dict:
    starts = datetime.fromisoformat(row["startsAt"])
    ends = datetime.fromisoformat(row["endsAt"])
    venue = row.get("venueName") or row["venueId"]
    return {
        "kind": "venue",
        "id": row["bookingId"],
        "summary": f"Venue booking at {venue}, {starts:%d %b %Y %H:%M} to {ends:%d %b %Y %H:%M} UTC",
    }


def _equipment_arrangement(row: dict) -> dict:
    item = row.get("equipmentName") or row["equipmentId"]
    return {
        "kind": "equipment",
        "id": row["reservationId"],
        "summary": f"Equipment reservation: {row['quantity']} x {item}",
    }


def affected_arrangements(event_id: str, authorization: str | None) -> list[dict]:
    """SPM-71 AC3: the event's confirmed venue bookings and the equipment
    reservations still holding stock for it, each named for the coordinator."""
    bookings = _arrangement_rows(
        "GET",
        f"{settings.venue_service_url}/venues/bookings",
        authorization,
        params={"eventId": event_id, "status": "approved"},
    )
    reservations = _arrangement_rows(
        "GET",
        f"{settings.equipment_service_url}/equipment/reservations",
        authorization,
        params={"eventId": event_id},
    )
    return [_venue_arrangement(row) for row in bookings] + [
        _equipment_arrangement(row) for row in reservations if row["status"] in HOLDING_RESERVATION_STATUSES
    ]


def flag_arrangements(event_id: str, reason: str, authorization: str | None) -> list[dict]:
    """SPM-71 AC4: mark the event's confirmed venue bookings and held equipment
    reservations as needing re-verification. Returns what was marked."""
    body = {"eventId": event_id, "reason": reason}
    bookings = _arrangement_rows(
        "POST", f"{settings.venue_service_url}/venues/bookings/reverification", authorization, json=body
    )
    reservations = _arrangement_rows(
        "POST", f"{settings.equipment_service_url}/equipment/reservations/reverification", authorization, json=body
    )
    return [_venue_arrangement(row) for row in bookings] + [_equipment_arrangement(row) for row in reservations]


# SPM-66: who may be assigned (AC8), the candidate list (AC2), and a
# coordinator's contact details (AC5) all come from user-service's directory.
USERS_UNREACHABLE = "The user directory could not be loaded right now. Please try again shortly."


def list_users(authorization: str | None) -> list[dict]:
    """Every ConnectSphere user (id, name, email, role, organisation).
    Unlike organisation_names() this is not best-effort: the callers cannot
    give a correct answer without it, so an unreachable service is a 503."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        response = _user_directory_client.get(f"{settings.user_service_url}/users", headers=headers)
    except httpx.HTTPError as exc:
        logger.info("list_users raised %r", exc)
        raise service_unavailable(USERS_UNREACHABLE) from exc
    if response.status_code != 200:
        logger.info("list_users got status %s", response.status_code)
        raise service_unavailable(USERS_UNREACHABLE)
    return response.json()


def send_notification(to: str, subject: str, body: str, authorization: str | None) -> bool:
    """Queue an email through notification-service. Best effort: callers have
    already saved their change, so a failure is logged rather than raised."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{settings.notification_service_url}/notifications",
                json={"to": to, "subject": subject, "body": body},
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.warning("notification to %s raised %r", to, exc)
        return False
    if response.status_code != 200:
        logger.warning("notification to %s got status %s", to, response.status_code)
        return False
    return True
