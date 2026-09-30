import logging

from fastapi import Depends

from app.core.config import settings
from app.routers.registration import router as registration_router
from shared.auth.deps import require_authenticated_user
from shared.config import parse_origins
from shared.openapi import create_service_app

logging.basicConfig(level=logging.INFO)

app = create_service_app(
    service_id="registration-service",
    title="Registration Service",
    description="""
Attendee registration for an event.

Eligibility is checked against event-service (event must be `confirmed`, registration enabled and open, capacity not exceeded). Duplicate emails for the same event are rejected.

The registration list is limited to the event's organiser and its assigned coordinator. It includes a capacity summary and each attendee's supplied details, registration time, and status.
""",
    port=8005,
    cors_origins=parse_origins(settings.cors_origin),
    tags_metadata=[
        {
            "name": "registrations",
            "description": "Register an attendee, or list who has registered when you organise or coordinate the event.",
        }
    ],
)

app.include_router(registration_router, dependencies=[Depends(require_authenticated_user)])
