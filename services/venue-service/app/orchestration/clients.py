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
