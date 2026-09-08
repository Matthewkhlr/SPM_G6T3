from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.models.user import User
from app.routers.user import router as user_router

SEED = [
    ("u1", "Alice Tan", "organiser@connectsphere.com", "organiser", "organiser123"),
    ("u2", "Ben Lee", "coordinator@connectsphere.com", "coordinator", "coord123"),
    ("u3", "Vinod Kumar", "venue@connectsphere.com", "venue", "venue123"),
    ("u4", "Tia Ho", "tech@connectsphere.com", "techsupport", "tech123"),
    ("u5", "Amy Wong", "attendee@connectsphere.com", "attendee", "attend123"),
]

app = FastAPI(title="user-service")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    init_db()
    db: Session = SessionLocal()
    try:
        if db.query(User).count() == 0:
            for user_id, name, email, role, password in SEED:
                db.add(User(userId=user_id, userName=name, email=email, role=role, password=password))
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"service": "user-service", "status": "ok"}


app.include_router(user_router)
