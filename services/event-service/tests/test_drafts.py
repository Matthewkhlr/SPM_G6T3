from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EventCreate, EventDraftUpsert
from app.services import event_service


def make_draft(db_session, organiser_id="u-organiser", **overrides):
    data = EventDraftUpsert(eventName="Q3 Partner Summit", **overrides)
    return event_service.create_draft(db_session, data, organiser_id=organiser_id, organisation_id="org-1")


def full_event_payload(**overrides):
    now = datetime.utcnow()
    defaults = dict(
        eventName="Q3 Partner Summit",
        purpose="Celebrate partners",
        description="A gathering",
        category="conference",
        proposedStartAt=now + timedelta(days=7),
        proposedEndAt=now + timedelta(days=7, hours=3),
        expectedAttendance=50,
    )
    defaults.update(overrides)
    return EventCreate(**defaults)


def test_create_draft_with_only_event_name_succeeds(db_session):
    created = make_draft(db_session)

    assert created.status == "draft"
    assert created.eventName == "Q3 Partner Summit"
    assert created.proposedStartAt is None
    assert created.proposedEndAt is None
    assert created.expectedAttendance == 0


def test_update_draft_preserves_fields_not_touched_by_a_later_save(db_session):
    created = make_draft(db_session, purpose="Initial purpose", venueRequirements="Needs a stage")

    # Simulate reopening the draft: the "form" is loaded with everything
    # previously entered, the organiser changes only one field, and the full
    # form is resent (full-overwrite semantics) — nothing else should be lost.
    resend = EventDraftUpsert(
        eventName="Q3 Partner Summit",
        purpose="Updated purpose",
        venueRequirements="Needs a stage",
    )
    updated = event_service.update_draft(db_session, created.eventId, resend, organiser_id="u-organiser")

    assert updated.purpose == "Updated purpose"
    assert updated.venueRequirements == "Needs a stage"
    assert updated.status == "draft"


def test_update_draft_by_different_organiser_is_forbidden(db_session):
    created = make_draft(db_session, organiser_id="u-organiser")

    with pytest.raises(HTTPException) as exc_info:
        event_service.update_draft(
            db_session, created.eventId, EventDraftUpsert(eventName="Hijacked"), organiser_id="u-someone-else"
        )

    assert exc_info.value.status_code == 403


def test_update_draft_on_already_submitted_event_conflicts(db_session):
    created = make_draft(db_session)
    event_service.submit_draft(db_session, created.eventId, full_event_payload(), organiser_id="u-organiser")

    with pytest.raises(HTTPException) as exc_info:
        event_service.update_draft(
            db_session, created.eventId, EventDraftUpsert(eventName="Too late"), organiser_id="u-organiser"
        )

    assert exc_info.value.status_code == 409


def test_submit_draft_moves_to_submitted_and_records_history(db_session):
    created = make_draft(db_session)

    result = event_service.submit_draft(db_session, created.eventId, full_event_payload(), organiser_id="u-organiser")

    assert result.status == "submitted"
    rows = (
        db_session.query(EventStatusHistory)
        .filter(EventStatusHistory.eventId == created.eventId)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].fromStatus == "draft"
    assert rows[0].toStatus == "submitted"
    assert rows[0].changedBy == "u-organiser"


def test_submit_draft_rejects_incomplete_payload():
    with pytest.raises(Exception):
        # eventName missing entirely — EventCreate's own validation should reject this
        # before it ever reaches the service layer, same as a fresh submission today.
        EventCreate(
            purpose="",
            description="",
            proposedStartAt=datetime.utcnow(),
            proposedEndAt=datetime.utcnow() + timedelta(hours=1),
            expectedAttendance=10,
        )


def test_list_my_drafts_returns_only_the_callers_own_drafts(db_session):
    mine = make_draft(db_session, organiser_id="u-organiser")
    make_draft(db_session, organiser_id="u-other")

    drafts = event_service.list_my_drafts(db_session, organiser_id="u-organiser")

    assert [d.eventId for d in drafts] == [mine.eventId]


def test_draft_does_not_appear_in_any_general_listing(db_session):
    make_draft(db_session)

    assert event_service.list_events(db_session) == []
    assert event_service.list_all_events(db_session) == []
    assert event_service.list_upcoming_events(db_session) == []
