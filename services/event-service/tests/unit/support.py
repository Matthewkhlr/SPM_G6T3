from datetime import datetime, timedelta
from unittest.mock import patch

from app.dao.event_assignment_dao import EventAssignmentDAO
from app.dao.event_dao import EventDAO
from app.dao.event_status_history_dao import EventStatusHistoryDAO
from app.models.event import Event
from app.schemas.event import EventCreate, EventDraftUpsert
from app.services.event_service import EventService
from shared.testing.cases import ServiceTestCase

START = datetime(2026, 10, 6, 9, 0)
END = datetime(2026, 10, 6, 17, 0)
ORGANISER = {"userId": "org-1", "organisationId": "o1", "role": "organiser", "userName": "Amy"}
COORDINATOR = {"userId": "coord-1", "role": "coordinator", "userName": "Ben"}
TECH = {"userId": "tech-1", "role": "techsupport", "userName": "Cara"}


def event_create(**overrides):
    data = dict(
        eventName="Summit",
        purpose="Share",
        description="A one-day summit",
        category="conference",
        proposedStartAt=START,
        proposedEndAt=END,
        expectedAttendance=20,
        venueRequirements="Hall",
        accessibilityNeeds="Ramp",
        equipmentRequirements="PA",
        layoutPreference="Theatre",
        registrationEnabled=True,
        registrationOpensAt=datetime(2026, 9, 1),
        registrationClosesAt=datetime(2026, 10, 1),
        capacity=20,
    )
    data.update(overrides)
    return EventCreate(**data)


def draft_payload(**overrides):
    data = dict(eventName="Draft summit")
    data.update(overrides)
    return EventDraftUpsert(**data)


def insert_event(db, **overrides):
    now = datetime.utcnow()
    data = dict(
        eventId="e-extra",
        organiserId="org-1",
        organisationId="o1",
        eventName="Extra",
        status="confirmed",
        proposedStartAt=datetime(2026, 12, 1, 9),
        proposedEndAt=datetime(2026, 12, 1, 17),
        expectedAttendance=1,
        submittedAt=now,
        createdAt=now,
        updatedAt=now,
    )
    data.update(overrides)
    row = Event(**data)
    db.add(row)
    db.commit()
    return row


class EventCase(ServiceTestCase):
    def setUp(self):
        super().setUp()
        self.counts = patch("app.services.event_service.registration_count", return_value=3)
        self.counts.start()
        self.service = EventService(
            self.db, EventDAO(self.db), EventAssignmentDAO(self.db), EventStatusHistoryDAO(self.db)
        )

    def tearDown(self):
        self.counts.stop()
        super().tearDown()
