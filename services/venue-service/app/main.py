from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.venue import router as venue_router
from shared.auth.deps import require_authenticated_user

app = FastAPI(title="venue-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"service": "venue-service", "status": "ok"}


app.include_router(venue_router, dependencies=[Depends(require_authenticated_user)])
