"""FastAPI dependency for enforcing authentication on service routes.

The browser calls services directly, so every service validates the Firebase
ID token it receives before serving protected endpoints.
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
