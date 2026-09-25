import logging
import time

import httpx

from app.core.config import settings
from shared.exceptions.http import forbidden, unauthorized

logger = logging.getLogger("perf.clients")

# Reused across calls so we're not paying a fresh TCP connect/teardown on
# every registration_count() call.
_registration_client = httpx.Client(timeout=3.0)


def registration_count(event_id: str, authorization: str | None = None) -> int:
    start = time.perf_counter()
    headers = {"Authorization": authorization} if authorization else {}
    try:
        response = _registration_client.get(
            f"{settings.registration_service_url}/registrations",
            params={"eventId": event_id},
            headers=headers,
        )
        if response.status_code == 200:
            return len(response.json())
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