import logging
import time

import httpx

from app.core.config import settings
from shared.exceptions.http import forbidden, unauthorized

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