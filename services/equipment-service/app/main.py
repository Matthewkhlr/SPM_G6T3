from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.equipment import router as equipment_router
from shared.auth.deps import require_authenticated_user
from shared.config import parse_origins

app = FastAPI(title="equipment-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(settings.cors_origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"service": "equipment-service", "status": "ok"}


app.include_router(equipment_router, dependencies=[Depends(require_authenticated_user)])
