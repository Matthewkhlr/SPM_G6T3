from fastapi import APIRouter, Request
from fastapi.responses import Response
import httpx

from app.core.config import settings
from app.middleware.auth import require_auth

router = APIRouter()

ROUTES = (
    ("/users", settings.user_service_url),
    ("/events", settings.event_service_url),
    ("/venues", settings.venue_service_url),
    ("/equipment", settings.equipment_service_url),
    ("/registrations", settings.registration_service_url),
    ("/notifications", settings.notification_service_url),
)


def _target_for(path: str) -> str | None:
    full = "/" + path
    for prefix, url in ROUTES:
        if full == prefix or full.startswith(prefix + "/"):
            return url
    return None


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    require_auth(request)
    target = _target_for(path)
    if not target:
        return Response(content='{"detail":"Not found"}', status_code=404, media_type="application/json")

    url = f"{target}/{path}"
    if request.url.query:
        url = f"{url}?{request.url.query}"

    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in {"host", "content-length"}
    }
    body = await request.body()
    async with httpx.AsyncClient() as client:
        upstream = await client.request(request.method, url, content=body, headers=headers, timeout=30.0)
    return Response(
        content=upstream.content,
        status_code=upstream.status_code,
        media_type=upstream.headers.get("content-type", "application/json"),
    )
