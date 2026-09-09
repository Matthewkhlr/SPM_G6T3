from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.equipment import router as equipment_router
from shared.auth.deps import require_authenticated_user

app = FastAPI(title="equipment-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"service": "equipment-service", "status": "ok"}


app.include_router(equipment_router, dependencies=[Depends(require_authenticated_user)])
