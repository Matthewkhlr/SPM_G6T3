from fastapi import Request

from shared.auth.tokens import verify_firebase_token
from shared.exceptions.http import unauthorized


def is_public(path: str) -> bool:
    return path == "/health"


def require_auth(request: Request) -> dict:
    if is_public(request.url.path):
        return {}
    header = request.headers.get("authorization", "")
    if not header.startswith("Bearer "):
        raise unauthorized()
    try:
        return verify_firebase_token(header[7:])
    except ValueError:
        raise unauthorized("Invalid or expired token")
