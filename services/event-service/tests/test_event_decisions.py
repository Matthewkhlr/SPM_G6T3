from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EventCreate


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


def history_rows(db_session, event_id):
    return (
        db_session.query(EventStatusHistory)
        .filter(EventStatusHistory.eventId == event_id)
        .all()
    )


def test_create_event_starts_submitted(event_service):
    created = make_event(event_service)
    assert created.status == "submitted"


def test_approve_event_moves_to_approved_and_records_history(event_service, db_session):
    created = make_event(event_service)

    result = event_service.approve_event(created.eventId, coordinator_id="u-coordinator")

    assert result.status == "approved"
    rows = history_rows(db_session, created.eventId)
    assert len(rows) == 1
    assert rows[0].fromStatus == "submitted"
    assert rows[0].toStatus == "approved"
    assert rows[0].changedBy == "u-coordinator"


def test_reject_event_moves_to_rejected_and_records_reason(event_service, db_session):
    created = make_event(event_service)

    result = event_service.reject_event(
        created.eventId, coordinator_id="u-coordinator", reason="Venue unavailable"
    )

    assert result.status == "rejected"
    rows = history_rows(db_session, created.eventId)
    assert len(rows) == 1
    assert rows[0].fromStatus == "submitted"
    assert rows[0].toStatus == "rejected"
    assert rows[0].note == "Venue unavailable"


def test_approve_event_already_decided_conflicts_and_leaves_event_unmutated(event_service, db_session):
    created = make_event(event_service)
    event_service.approve_event(created.eventId, coordinator_id="u-coordinator")

    with pytest.raises(HTTPException) as exc_info:
        event_service.approve_event(created.eventId, coordinator_id="u-coordinator-2")

    assert exc_info.value.status_code == 409
    # Still approved from the first call, no second history row.
    result = event_service.get_event(created.eventId)
    assert result.status == "approved"
    assert len(history_rows(db_session, created.eventId)) == 1


def test_reject_event_on_missing_event_raises_404(event_service):
    with pytest.raises(HTTPException) as exc_info:
        event_service.reject_event("does-not-exist", coordinator_id="u-coordinator")

    assert exc_info.value.status_code == 404
