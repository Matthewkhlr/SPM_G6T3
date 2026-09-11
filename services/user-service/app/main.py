from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers.user import router as user_router
from shared.config import parse_origins

app = FastAPI(title="user-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_origins(settings.cors_origin),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"service": "user-service", "status": "ok"}


app.include_router(user_router)
