from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EventCreate
from app.services import event_service


def make_event(db_session, **overrides):
    now = datetime.utcnow()
    data = EventCreate(
        eventName="Q3 Partner Summit",
        expectedAttendance=50,
        proposedStartAt=now + timedelta(days=7),
        proposedEndAt=now + timedelta(days=7, hours=3),
        **overrides,
    )
    return event_service.create_event(db_session, data, organiser_id="u-organiser", organisation_id="org-1")


def history_rows(db_session, event_id):
    return (
        db_session.query(EventStatusHistory)
        .filter(EventStatusHistory.eventId == event_id)
        .all()
    )


def test_create_event_starts_submitted(db_session):
    created = make_event(db_session)
    assert created.status == "submitted"


def test_approve_event_moves_to_approved_and_records_history(db_session):
    created = make_event(db_session)

    result = event_service.approve_event(db_session, created.eventId, coordinator_id="u-coordinator")

    assert result.status == "approved"
    rows = history_rows(db_session, created.eventId)
    assert len(rows) == 1
    assert rows[0].fromStatus == "submitted"
    assert rows[0].toStatus == "approved"
    assert rows[0].changedBy == "u-coordinator"


def test_reject_event_moves_to_rejected_and_records_reason(db_session):
    created = make_event(db_session)

    result = event_service.reject_event(
        db_session, created.eventId, coordinator_id="u-coordinator", reason="Venue unavailable"
    )

    assert result.status == "rejected"
    rows = history_rows(db_session, created.eventId)
    assert len(rows) == 1
    assert rows[0].fromStatus == "submitted"
    assert rows[0].toStatus == "rejected"
    assert rows[0].note == "Venue unavailable"


def test_approve_event_already_decided_conflicts_and_leaves_event_unmutated(db_session):
    created = make_event(db_session)
    event_service.approve_event(db_session, created.eventId, coordinator_id="u-coordinator")

    with pytest.raises(HTTPException) as exc_info:
        event_service.approve_event(db_session, created.eventId, coordinator_id="u-coordinator-2")

    assert exc_info.value.status_code == 409
    # Still approved from the first call, no second history row.
    result = event_service.get_event(db_session, created.eventId)
    assert result.status == "approved"
    assert len(history_rows(db_session, created.eventId)) == 1


def test_reject_event_on_missing_event_raises_404(db_session):
    with pytest.raises(HTTPException) as exc_info:
        event_service.reject_event(db_session, "does-not-exist", coordinator_id="u-coordinator")

    assert exc_info.value.status_code == 404
