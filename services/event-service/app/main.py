from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.models.event import Event
from app.routers.event import router as event_router

app = FastAPI(title="event-service")
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
    now = datetime.utcnow()
    seed = [
        ("e1", "AI in Events Summit", "confirmed", True, now - timedelta(days=5), now + timedelta(days=3), 3),
        ("e2", "Venue Ops Workshop", "confirmed", True, now - timedelta(days=2), now + timedelta(days=10), 2),
        ("e3", "Partner Networking Night", "planning", False, now + timedelta(days=4), now + timedelta(days=14), 100),
        ("e4", "Q1 Client Briefing", "confirmed", True, now + timedelta(days=2), now + timedelta(days=20), 50),
    ]
    db: Session = SessionLocal()
    try:
        if db.query(Event).count() == 0:
            for row in seed:
                db.add(Event(
                    eventId=row[0], eventName=row[1], status=row[2], registrationEnabled=row[3],
                    registrationOpensAt=row[4], registrationClosesAt=row[5], capacity=row[6],
                ))
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"service": "event-service", "status": "ok"}


app.include_router(event_router)
