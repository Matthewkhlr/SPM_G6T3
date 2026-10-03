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


def _current_user(authorization: str | None, role: str, forbidden_message: str) -> dict:
    """Resolve the caller's bearer token to their ConnectSphere user record.

    A Firebase token only carries uid/email — role and organisation live in
    user-service's database, which this service cannot read directly. So the
    token is forwarded to user-service's /users/me, which re-verifies it and
    maps it to the local user via firebase_uid. ``role`` is the single role
    this call accepts; ``forbidden_message`` is the 403 detail when it does not match.
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
    if user.get("role") != role:
        raise forbidden(forbidden_message)
    return user


def current_organiser(authorization: str | None) -> dict:
    return _current_user(authorization, "organiser", "Only event organisers can create events")


def current_technical_support(authorization: str | None) -> dict:
    return _current_user(
        authorization, "techsupport", "Only technical support staff can view upcoming events"
    )


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


def _arrangement_rows(
    method: str, url: str, authorization: str | None, unreachable: str = ARRANGEMENTS_UNREACHABLE, **kwargs
):
    """The JSON body of a call whose answer a change depends on; 503 with
    `unreachable` when it cannot be had, so nothing is saved unchecked."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.request(method, url, headers=headers, **kwargs)
    except httpx.HTTPError as exc:
        logger.info("%s %s raised %r", method, url, exc)
        raise service_unavailable(unreachable) from exc
    if response.status_code != 200:
        logger.info("%s %s got status %s", method, url, response.status_code)
        raise service_unavailable(unreachable)
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


# SPM-90: registration settings are only saved once the registrations and the
# venue booking they depend on have been checked.
REGISTRATIONS_UNREACHABLE = (
    "Registrations could not be checked right now, so the change was not saved. Please try again shortly."
)
VENUE_UNREACHABLE = "The venue booking could not be checked right now, so the change was not saved. Please try again shortly."


def current_registration_count(event_id: str, authorization: str | None) -> int:
    """SPM-90 AC4/AC5: attendees currently registered. Unlike registration_count()
    this is not best effort: a capacity check against 0 would let a change
    through that the real count forbids."""
    body = _arrangement_rows(
        "GET",
        f"{settings.registration_service_url}/registrations/count",
        authorization,
        REGISTRATIONS_UNREACHABLE,
        params={"eventId": event_id},
    )
    return int(body["count"])


def registered_attendees(event_id: str, authorization: str | None) -> list[dict]:
    """SPM-90 AC5: the attendees still registered, with userId and email, so
    they can be told registration was turned off."""
    roster = _arrangement_rows(
        "GET",
        f"{settings.registration_service_url}/registrations",
        authorization,
        REGISTRATIONS_UNREACHABLE,
        params={"eventId": event_id, "includeWithdrawn": "false"},
    )
    return [row for row in roster["attendees"] if row.get("status") == "registered"]


def booked_venue_capacities(event_id: str, layout: str | None, authorization: str | None) -> list[dict]:
    """SPM-90 AC3: for each confirmed venue booking of the event, the venue and
    how many it holds in the event's layout. A booking does not record a
    layout, so the event's own layout is the booked one; without one, or one
    the venue does not offer, the venue's largest layout applies, as in the
    suitability check (SPM-62)."""
    bookings = _arrangement_rows(
        "GET",
        f"{settings.venue_service_url}/venues/bookings",
        authorization,
        VENUE_UNREACHABLE,
        params={"eventId": event_id, "status": "approved"},
    )
    capacities = []
    for booking in bookings:
        venue = _arrangement_rows(
            "GET", f"{settings.venue_service_url}/venues/{booking['venueId']}", authorization, VENUE_UNREACHABLE
        )
        by_layout = {row["name"].lower(): row["capacity"] for row in venue.get("layouts", [])}
        in_layout = by_layout.get(layout.lower()) if layout else None
        capacities.append(
            {
                "venueName": venue["name"],
                "layout": layout if in_layout is not None else None,
                "capacity": in_layout if in_layout is not None else venue["capacity"],
            }
        )
    return capacities


def record_notification(
    user_id: str, event_id: str, kind: str, title: str, body: str, authorization: str | None
) -> bool:
    """SPM-90: put a notification in `user_id`'s in-app inbox. Staff may notify
    another user. Best effort: callers have already saved their change."""
    headers = {"Authorization": authorization} if authorization else {}
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.post(
                f"{settings.notification_service_url}/notifications/records",
                json={"userId": user_id, "eventId": event_id, "type": kind, "title": title, "body": body},
                headers=headers,
            )
    except httpx.HTTPError as exc:
        logger.warning("in-app notification to %s raised %r", user_id, exc)
        return False
    if response.status_code != 201:
        logger.warning("in-app notification to %s got status %s", user_id, response.status_code)
        return False
    return True


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
