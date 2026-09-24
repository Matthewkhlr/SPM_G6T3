from fastapi import Depends

from app.core.config import settings
from app.routers.notification import router as notification_router
from shared.auth.deps import require_authenticated_user
from shared.config import parse_origins
from shared.openapi import create_service_app

app = create_service_app(
    service_id="notification-service",
    title="Notification Service",
    description="""
Queues an email notification.

Delivery is currently a stub: the payload is logged and the response status is `queued`. Rows may also exist in the notification schema from seed data.
""",
    port=8006,
    cors_origins=parse_origins(settings.cors_origin),
    tags_metadata=[
        {
            "name": "notifications",
            "description": "Queue an outbound email notification.",
        }
    ],
)

app.include_router(notification_router, dependencies=[Depends(require_authenticated_user)])
