from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.models.attendee_registration import AttendeeRegistration
from app.models.registration import Registration
from app.routers.registration import router as registration_router

app = FastAPI(title="registration-service")
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
        if db.query(Registration).count() == 0:
            db.add(Registration(registrationId="reg-e1", eventId="e1", capacity=3))
            db.add(Registration(registrationId="reg-e2", eventId="e2", capacity=2))
            db.add(AttendeeRegistration(
                attendeeRegistrationId="r1", eventId="e1", attendeeName="Demo Attendee",
                attendeeEmail="one@example.com", userId=None, createdAt=datetime.utcnow(),
            ))
            db.add(AttendeeRegistration(
                attendeeRegistrationId="r2", eventId="e2", attendeeName="Full One",
                attendeeEmail="full1@example.com", userId=None, createdAt=datetime.utcnow(),
            ))
            db.add(AttendeeRegistration(
                attendeeRegistrationId="r3", eventId="e2", attendeeName="Full Two",
                attendeeEmail="full2@example.com", userId=None, createdAt=datetime.utcnow(),
            ))
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"service": "registration-service", "status": "ok"}


app.include_router(registration_router)
