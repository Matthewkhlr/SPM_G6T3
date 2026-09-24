from fastapi import Depends

from app.core.config import settings
from app.routers.venue import router as venue_router
from shared.auth.deps import require_authenticated_user
from shared.config import parse_origins
from shared.openapi import create_service_app

app = create_service_app(
    service_id="venue-service",
    title="Venue Service",
    description="""
Venue catalogue and booking workflow.

Coordinators create booking requests. Venue staff approve or reject them. Catalogue reads (`GET /venues`) are available to any authenticated user.
""",
    port=8003,
    cors_origins=parse_origins(settings.cors_origin),
    tags_metadata=[
        {
            "name": "venues",
            "description": "List/get venues and create, approve, or reject venue bookings.",
        }
    ],
)

app.include_router(venue_router, dependencies=[Depends(require_authenticated_user)])
