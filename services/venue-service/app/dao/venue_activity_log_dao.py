from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.venue_activity_log import VenueActivityLog


class VenueActivityLogDAO:
    def __init__(self, db: Session):
        self.db = db

    def log(self, venue_id: str, action: str, caller: dict, changes: dict) -> None:
        self.db.add(
            VenueActivityLog(
                logId=str(uuid4()),
                venueId=venue_id,
                action=action,
                changedBy=caller["userId"],
                changedByName=caller.get("userName", ""),
                changedByRole=caller.get("role", ""),
                changes=changes,
                createdAt=datetime.utcnow(),
            )
        )

    def list_for_venue(self, venue_id: str) -> list[VenueActivityLog]:
        return (
            self.db.query(VenueActivityLog)
            .filter(VenueActivityLog.venueId == venue_id)
            .order_by(VenueActivityLog.createdAt.desc())
            .all()
        )
