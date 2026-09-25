import logging

from fastapi import Depends

from app.core.config import settings
from app.routers.event import router as event_router
from shared.auth.deps import require_authenticated_user
from shared.config import parse_origins
from shared.openapi import create_service_app

logging.basicConfig(level=logging.INFO)

app = create_service_app(
    service_id="event-service",
    title="Event Service",
    description="""
Owns event requests and coordinator assignment.

`organiserId` / `organisationId` are taken from the caller's identity, not the request body. Registration counts on event payloads are fetched live from registration-service.

New events start at status `created`. Seed data also uses `planning` and `confirmed`.
""",
    port=8002,
    cors_origins=parse_origins(settings.cors_origin),
    tags_metadata=[
        {
            "name": "events",
            "description": "Create and list events, look up one event, and assign a coordinator.",
        }
    ],
)

app.include_router(event_router, dependencies=[Depends(require_authenticated_user)])
