"""Shared FastAPI / OpenAPI setup for every microservice."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

API_VERSION = "0.1.0"

AUTH_NOTES = """
## Authentication

Protected routes expect `Authorization: Bearer <Firebase ID token>`.

In Swagger UI click **Authorize**, paste the ID token only (not the word `Bearer`), then use **Try it out**.

`GET /health` is public and does not need a token.

How to get a token locally: sign in through the Vue app, then copy the `Authorization` header from any API request in the Network tab. Paste the token only — not the word `Bearer`.
"""

ERROR_RESPONSES = {
    401: {
        "description": "Missing or invalid Firebase ID token.",
        "content": {"application/json": {"example": {"detail": "Authentication required"}}},
    },
    403: {
        "description": "Authenticated, but this role cannot perform the action.",
        "content": {
            "application/json": {
                "example": {"detail": "You do not have permission to perform this action"}
            }
        },
    },
    404: {
        "description": "Resource not found.",
        "content": {"application/json": {"example": {"detail": "Not found"}}},
    },
    409: {
        "description": "Conflict with an existing resource or business rule.",
        "content": {"application/json": {"example": {"detail": "Conflict"}}},
    },
    422: {
        "description": "The request was understood, but a quantity rule rejected it.",
        "content": {
            "application/json": {
                "example": {"detail": "Out-of-service counts cannot add up to more than the total owned"}
            }
        },
    },
    503: {
        "description": "A downstream service is unavailable.",
        "content": {"application/json": {"example": {"detail": "Could not verify identity"}}},
    },
}


def error_responses(*codes: int) -> dict:
    return {code: ERROR_RESPONSES[code] for code in codes}


def create_service_app(
    *,
    service_id: str,
    title: str,
    description: str,
    port: int,
    cors_origins: list[str],
    tags_metadata: list[dict] | None = None,
) -> FastAPI:
    tags = [
        {
            "name": "health",
            "description": "Public liveness check. No Firebase token required.",
        }
    ]
    tags.extend(tags_metadata or [])

    app = FastAPI(
        title=title,
        description=f"{description.strip()}\n{AUTH_NOTES}",
        version=API_VERSION,
        openapi_tags=tags,
        servers=[{"url": f"http://localhost:{port}", "description": "Local"}],
        swagger_ui_parameters={"persistAuthorization": True, "docExpansion": "list"},
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get(
        "/health",
        tags=["health"],
        summary="Liveness check",
        description="Returns immediately if this process is up. Used by local scripts and load balancers.",
    )
    def health():
        return {"service": service_id, "status": "ok"}

    return app
