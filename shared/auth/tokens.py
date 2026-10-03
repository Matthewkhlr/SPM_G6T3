"""Identity tokens.

Auth is delegated to Firebase: clients sign in with Firebase and send the
resulting ID token as the bearer token. Services verify it here with the
Firebase Admin SDK, which needs a service account key. Provide it via
FIREBASE_CREDENTIALS_JSON (the whole service account JSON, single-quoted) in
the repo-root .env — gitignored, shared with the team out-of-band, and
loaded here directly so every service picks it up regardless of its own cwd.
A locally-downloaded key file also works via FIREBASE_CREDENTIALS_PATH /
GOOGLE_APPLICATION_CREDENTIALS.
"""
import json
import os
from pathlib import Path

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import auth as firebase_auth, credentials

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

_firebase_app: firebase_admin.App | None = None


def get_firebase_app() -> firebase_admin.App:
    global _firebase_app
    if _firebase_app is not None:
        return _firebase_app

    cred_json = os.getenv("FIREBASE_CREDENTIALS_JSON")
    if cred_json:
        cred = credentials.Certificate(json.loads(cred_json))
    else:
        cred_path = os.getenv("FIREBASE_CREDENTIALS_PATH") or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        if not cred_path:
            raise RuntimeError(
                "Firebase Admin is not configured: set FIREBASE_CREDENTIALS_JSON "
                "(service account JSON) or FIREBASE_CREDENTIALS_PATH (a key file)."
            )
        cred = credentials.Certificate(cred_path)
    _firebase_app = firebase_admin.initialize_app(cred)
    return _firebase_app


def verify_firebase_token(token: str) -> dict:
    """Verify a Firebase ID token, returning its decoded claims (uid, email, ...)."""
    try:
        # Local clocks can sit a few seconds behind Google's token iat.
        return firebase_auth.verify_id_token(
            token, app=get_firebase_app(), clock_skew_seconds=60
        )
    except Exception as exc:
        raise ValueError("Invalid or expired token") from exc
