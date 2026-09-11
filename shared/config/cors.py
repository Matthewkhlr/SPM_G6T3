"""Shared parsing for the CORS allow-list every service configures.

Browsers treat http://localhost:5173 and http://127.0.0.1:5173 as different
origins even though they are the same dev server, and CORSMiddleware matches
the Origin header as an exact string. Allowing only one of them means the app
silently fails — the preflight is rejected with 400 and the real request is
never sent — depending on which URL the developer happened to type.

So `cors_origin` holds a comma-separated list rather than a single value.
"""


def parse_origins(raw: str) -> list[str]:
    """Split a comma-separated origin list, ignoring blanks and stray spaces."""
    return [origin.strip() for origin in raw.split(",") if origin.strip()]
