"""Identity tokens.

Production: verify Firebase ID tokens (see verify_firebase_token).
Local/demo: HS256 JWT issued by user-service until Firebase is wired.
"""
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

SECRET = "connectsphere-dev-secret"
ALGORITHM = "HS256"


def create_access_token(payload: dict, hours: int = 8) -> str:
    data = {**payload, "exp": datetime.now(timezone.utc) + timedelta(hours=hours)}
    return jwt.encode(data, SECRET, algorithm=ALGORITHM)


def verify_firebase_token(token: str) -> dict:
    """Replace with firebase_admin.auth.verify_id_token(token) when Firebase is configured."""
    raise NotImplementedError("Firebase Admin is not configured yet")


def verify_bearer_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise ValueError("Invalid or expired token") from exc
