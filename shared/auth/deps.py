"""FastAPI dependency for enforcing authentication on service routes.

The browser calls services directly, so every service validates the Firebase
ID token it receives before serving protected endpoints.
"""
import logging
import time

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from shared.exceptions.http import unauthorized

from .tokens import verify_firebase_token

logger = logging.getLogger("perf.auth")

bearer_scheme = HTTPBearer(
    auto_error=False,
    bearerFormat="JWT",
    scheme_name="FirebaseBearer",
    description=(
        "Firebase ID token from the signed-in client. "
        "Paste the token only — Swagger adds the `Bearer ` prefix."
    ),
)


def require_authenticated_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise unauthorized()
    start = time.perf_counter()
    try:
        return verify_firebase_token(credentials.credentials)
    except ValueError:
        raise unauthorized("Invalid or expired token")
    finally:
        logger.info("verify_firebase_token took %.3fs", time.perf_counter() - start)


def forwarded_bearer(
    authorization: str | None = Header(default=None, include_in_schema=False),
) -> str | None:
    """Raw `Authorization` header for forwarding to user-service.

    Hidden from OpenAPI — Swagger's Authorize button already sends this header.
    """
    return authorization
