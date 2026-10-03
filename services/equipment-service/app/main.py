from fastapi import Depends

from app.core.config import settings
from app.routers.equipment import router as equipment_router
from shared.auth.deps import require_authenticated_user
from shared.config import parse_origins
from shared.openapi import create_service_app

app = create_service_app(
    service_id="equipment-service",
    title="Equipment Service",
    description="""
Equipment catalogue, coordinator requests, and technical-support review.

Coordinators file requests. Technical support reviews (approve/reject) and reserves approved stock.
""",
    port=8004,
    cors_origins=parse_origins(settings.cors_origin),
    tags_metadata=[
        {
            "name": "equipment",
            "description": "List/get equipment, create requests, review requests, and reserve approved stock.",
        }
    ],
)

app.include_router(equipment_router, dependencies=[Depends(require_authenticated_user)])
