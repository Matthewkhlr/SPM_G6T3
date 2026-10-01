from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.event import Event


class EventDAO:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, event_id: str) -> Event | None:
        return self.db.query(Event).filter(Event.eventId == event_id).first()

    def list_excluding_draft(self) -> list[Event]:
        return self.db.query(Event).filter(Event.status.notin_(["draft", "discarded"])).all()

    def list_excluding_statuses(self, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.status.notin_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_by_status(self, status: str) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.status == status)
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_by_statuses_ordered_by_submitted(self, statuses: list[str]) -> list[Event]:
        """Oldest submittedAt first - i.e. longest-waiting request first."""
        return (
            self.db.query(Event)
            .filter(Event.status.in_(statuses))
            .order_by(Event.submittedAt.asc())
            .all()
        )

    def list_by_statuses_ordered_by_proposed_start(self, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.status.in_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_upcoming_excluding_statuses(self, after: datetime, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.proposedEndAt >= after)
            .filter(Event.status.notin_(statuses))
            .order_by(Event.proposedStartAt.asc())
            .all()
        )

    def list_drafts_by_organiser(self, organiser_id: str) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.organiserId == organiser_id, Event.status == "draft")
            .order_by(Event.updatedAt.desc())
            .all()
        )

    def list_by_organiser_excluding_statuses(self, organiser_id: str, statuses: list[str]) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.organiserId == organiser_id, Event.status.notin_(statuses))
            .order_by(Event.updatedAt.desc())
            .all()
        )

    def count_by_coordinator_excluding_statuses(self, statuses: list[str]) -> dict[str, int]:
        """coordinatorId -> how many of their assigned events are not in `statuses`."""
        rows = (
            self.db.query(Event.coordinatorId, func.count(Event.eventId))
            .filter(Event.coordinatorId.isnot(None), Event.status.notin_(statuses))
            .group_by(Event.coordinatorId)
            .all()
        )
        return {coordinator_id: count for coordinator_id, count in rows}

    def add(self, row: Event) -> None:
        self.db.add(row)
