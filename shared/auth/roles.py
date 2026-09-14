"""Cross-service role resolution.

A Firebase token only carries uid/email — a user's role lives only in
user-service's database. A service that needs to gate an action by role
(but isn't user-service itself) forwards the caller's bearer token to
user-service's /users/me, which re-verifies it and returns the local user
record. This mirrors event-service's existing `current_organiser` pattern,
generalized to an arbitrary allowed-role set for reuse across services.
"""
import httpx

from shared.exceptions.http import forbidden, service_unavailable, unauthorized


def resolve_caller(
    authorization: str | None,
    user_service_url: str,
    allowed_roles: set[str] | None = None,
    timeout: float = 5.0,
) -> dict:
    """Resolve the caller's bearer token to their user record, optionally role-gated.

    Raises 401 if the token itself is missing/invalid, 503 if user-service
    can't be reached (a dependency failure, not an auth failure), and 403 if
    the caller's role isn't in allowed_roles.
    """
    if not authorization:
        raise unauthorized()
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                f"{user_service_url}/users/me",
                headers={"Authorization": authorization},
            )
    except httpx.HTTPError as exc:
        raise service_unavailable("Could not verify identity") from exc

    if response.status_code == 401:
        raise unauthorized("Invalid or expired token")
    if response.status_code != 200:
        raise service_unavailable("Could not verify identity")

    user = response.json()
    if allowed_roles is not None and user.get("role") not in allowed_roles:
        raise forbidden("You do not have permission to perform this action")
    return user
