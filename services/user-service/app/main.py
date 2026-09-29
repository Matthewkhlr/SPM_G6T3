from app.core.config import settings
from app.routers.organisation import router as organisation_router
from app.routers.user import router as user_router
from shared.config import parse_origins
from shared.openapi import create_service_app

app = create_service_app(
    service_id="user-service",
    title="User Service",
    description="""
Identifies ConnectSphere users from a Firebase ID token and exposes the user directory.

Other services call `GET /users/me` with the caller's bearer token to resolve `userId`, `role`, and `organisationId`.

**Roles:** `organiser` · `coordinator` · `venue` · `techsupport` · `attendee`
""",
    port=8001,
    cors_origins=parse_origins(settings.cors_origin),
    tags_metadata=[
        {
            "name": "users",
            "description": "Current user profile (from the bearer token) and the user directory.",
        },
        {
            "name": "organisations",
            "description": "Organisation directory - lets other services resolve organisationId to a name.",
        },
    ],
)

app.include_router(user_router)
app.include_router(organisation_router)
