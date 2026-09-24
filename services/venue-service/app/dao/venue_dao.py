from sqlalchemy.orm import Session

from app.models.venue_info import VenueInfo


class VenueDAO:
    def __init__(self, db: Session):
        self.db = db

    def list(self, include_retired: bool = False) -> list[VenueInfo]:
        query = self.db.query(VenueInfo)
        if not include_retired:
            query = query.filter(VenueInfo.isActive.is_(True))
        return query.all()

    def get_by_id(self, venue_id: str) -> VenueInfo | None:
        return self.db.query(VenueInfo).filter(VenueInfo.venueId == venue_id).first()

    def add(self, row: VenueInfo) -> None:
        self.db.add(row)
