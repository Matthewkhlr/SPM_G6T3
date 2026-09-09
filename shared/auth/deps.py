"""FastAPI dependency for enforcing authentication on a service's own routes.

Every request already passes through the API gateway, which verifies the
Firebase ID token before proxying. This dependency exists so each service
also verifies it independently — defense in depth, so a service is never
unauthenticated just because it's reachable directly (e.g. its port is
exposed in local dev, or the gateway is ever misconfigured/bypassed).

This checks identity only (authentication). It does not check role or
"relationship to a resource" — that's authorization, handled separately.
"""
from fastapi import Header

from shared.exceptions.http import unauthorized

from .tokens import verify_firebase_token


def require_authenticated_user(authorization: str | None = Header(default=None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise unauthorized()
    try:
        return verify_firebase_token(authorization[7:])
    except ValueError:
        raise unauthorized("Invalid or expired token")
