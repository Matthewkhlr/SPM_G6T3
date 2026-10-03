import httpx

from app.core.config import settings
from shared.exceptions.http import not_found, service_unavailable

EVENT_UNREACHABLE = "The event's details could not be loaded right now. Please try again shortly."


def fetch_event_coordinator(event_id: str, authorization: str) -> str | None:
    """SPM-46: events live in event-service, so who is assigned to an event is
    read from there at the moment of each request, forwarding the caller's
    own token. Reading it fresh each time is what makes a reassignment take
    effect immediately."""
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
    return response.json().get("coordinatorId")
