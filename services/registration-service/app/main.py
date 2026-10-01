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

The registration list is limited to the event's organiser and its assigned coordinator. It includes a capacity summary and each attendee's supplied details, registration time, and status. An attendee asking for that list receives only how many places remain.

An attendee can withdraw their own registration while the event has not started and has not been completed or cancelled. The row is kept with status `withdrawn`, the place is released, and they can register again while the period is open and a place remains.
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
