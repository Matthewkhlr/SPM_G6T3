import logging

import httpx

from app.core.config import settings
from app.schemas.venue import EventFacts
from shared.exceptions.http import not_found, service_unavailable

EVENT_UNREACHABLE = "The event's details could not be loaded right now. Please try again shortly."


def fetch_event_facts(event_id: str, authorization: str) -> EventFacts:
    """Events live in event-service, so an event's attendance, layout and
    dates are read from there, forwarding the caller's own token."""
    try:
        response = httpx.get(
            f"{settings.event_service_url}/events/{event_id}",
            headers={"Authorization": authorization},
            timeout=5.0,
        )
    except httpx.HTTPError as exc:
        raise service_unavailable(EVENT_UNREACHABLE) from exc
    if response.status_code == 404:
        raise not_found("Event not found")
    if response.status_code != 200:
        raise service_unavailable(EVENT_UNREACHABLE)
    return EventFacts.model_validate(response.json())


logger = logging.getLogger("venue.notifications")


def notify_venue_staff(subject: str, body: str, authorization: str) -> int:
    """SPM-63 AC5 and AC8: email every Venue Staff user through notification-service.

    Best effort: the request itself is already saved, so a notification that
    cannot be sent is logged rather than undoing the coordinator's request.
    Returns how many notifications were accepted.
    """
    try:
        users = httpx.get(
            f"{settings.user_service_url}/users", headers={"Authorization": authorization}, timeout=5.0
        )
        if users.status_code != 200:
            logger.warning("could not list Venue Staff: status %s", users.status_code)
            return 0
        sent = 0
        for user in users.json():
            if user.get("role") != "venue":
                continue
            response = httpx.post(
                f"{settings.notification_service_url}/notifications",
                json={"to": user["email"], "subject": subject, "body": body},
                headers={"Authorization": authorization},
                timeout=5.0,
            )
            if response.status_code == 200:
                sent += 1
            else:
                logger.warning("notification to %s failed: status %s", user["email"], response.status_code)
        return sent
    except httpx.HTTPError as exc:
        logger.warning("could not notify Venue Staff: %r", exc)
        return 0
