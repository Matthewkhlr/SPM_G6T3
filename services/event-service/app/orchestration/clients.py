import httpx

from app.core.config import settings
from shared.exceptions.http import forbidden, unauthorized


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
