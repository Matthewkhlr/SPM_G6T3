from datetime import datetime, timedelta

from app.models.event import Event
from app.schemas.event import EventAssignmentCreate, EventCreate


def make_event(event_service, **overrides):
    now = datetime.utcnow()
    data = EventCreate(
        eventName="Q3 Partner Summit",
        expectedAttendance=50,
        proposedStartAt=now + timedelta(days=7),
        proposedEndAt=now + timedelta(days=7, hours=3),
        **overrides,
    )
    return event_service.create_event(data, organiser_id="u-organiser", organisation_id="org-1")


def test_list_confirmed_events_is_empty_until_something_reaches_confirmed(event_service):
    make_event(event_service)

    assert event_service.list_confirmed_events() == []


def test_assign_coordinator_writes_an_assignment_and_updates_the_event(event_service, db_session):
    created = make_event(event_service)

    assignment = event_service.assign_coordinator(
        created.eventId, EventAssignmentCreate(coordinatorId="u-coordinator"), assigned_by="u-coordinator"
    )

    assert assignment.eventId == created.eventId
    assert assignment.coordinatorId == "u-coordinator"
    assert assignment.assignedBy == "u-coordinator"

    row = db_session.query(Event).filter(Event.eventId == created.eventId).first()
    assert row.coordinatorId == "u-coordinator"
