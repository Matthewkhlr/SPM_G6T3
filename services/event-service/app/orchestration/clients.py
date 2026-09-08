import httpx

from app.core.config import settings


def registration_count(event_id: str) -> int:
    try:
        with httpx.Client(timeout=3.0) as client:
            response = client.get(
                f"{settings.registration_service_url}/registrations",
                params={"eventId": event_id},
            )
            if response.status_code == 200:
                return len(response.json())
    except httpx.HTTPError:
        return 0
    return 0
