import json

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, init_db
from app.models.venue_info import VenueInfo
from app.routers.venue import router as venue_router

SEED = [
    ("v1", "Marina Hall A", "3 Harbourfront Ave, Level 2", 300, ["Projector", "PA system", "Video-conferencing", "Stage"], "Wheelchair accessible, accessible restrooms nearby", ["Theatre", "Classroom", "Banquet"], "Mon–Sun, 8:00 AM – 10:00 PM", 60),
    ("v2", "Riverside Room 204", "3 Harbourfront Ave, Level 2", 80, ["Projector", "Whiteboard"], "Wheelchair accessible", ["Boardroom", "Classroom"], "Mon–Sat, 8:00 AM – 8:00 PM", 30),
    ("v3", "Exhibition Hall B", "12 Convention Way", 500, ["Loading dock", "PA system", "Booth power points"], "Wheelchair accessible, accessible restrooms nearby", ["Exhibition", "Theatre"], "Mon–Sun, 7:00 AM – 11:00 PM", 120),
    ("v4", "Skyline Boardroom", "3 Harbourfront Ave, Level 18", 20, ["Video-conferencing", "Smart TV"], "Wheelchair accessible", ["Boardroom"], "Mon–Fri, 8:00 AM – 6:00 PM", 15),
]

app = FastAPI(title="venue-service")
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
        if db.query(VenueInfo).count() == 0:
            for row in SEED:
                db.add(VenueInfo(
                    venueId=row[0], name=row[1], location=row[2], capacity=row[3],
                    facilities=json.dumps(row[4]), accessibility=row[5],
                    layouts=json.dumps(row[6]), operatingHours=row[7], turnaroundMinutes=row[8],
                ))
            db.commit()
    finally:
        db.close()


@app.get("/health")
def health():
    return {"service": "venue-service", "status": "ok"}


app.include_router(venue_router)
