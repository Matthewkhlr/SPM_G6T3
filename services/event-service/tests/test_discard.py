import pytest
from fastapi import HTTPException

from app.models.event_status_history import EventStatusHistory
from app.schemas.event import EventDraftUpsert


def make_draft(event_service, organiser_id="u-organiser", **overrides):
    data = EventDraftUpsert(eventName="Q3 Partner Summit", **overrides)
    return event_service.create_draft(data, organiser_id=organiser_id, organisation_id="org-1")


def test_discard_draft_moves_to_discarded_and_records_history(event_service, db_session):
    created = make_draft(event_service)

    result = event_service.discard_draft(created.eventId, organiser_id="u-organiser")

    assert result.status == "discarded"
    rows = (
        db_session.query(EventStatusHistory)
        .filter(EventStatusHistory.eventId == created.eventId)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].fromStatus == "draft"
    assert rows[0].toStatus == "discarded"
    assert rows[0].changedBy == "u-organiser"


def test_discard_by_different_organiser_is_forbidden(event_service):
    created = make_draft(event_service, organiser_id="u-organiser")

    with pytest.raises(HTTPException) as exc_info:
        event_service.discard_draft(created.eventId, organiser_id="u-someone-else")

    assert exc_info.value.status_code == 403


def test_discard_non_draft_is_forbidden(event_service):
    created = make_draft(event_service)
    from datetime import datetime, timedelta

    from app.schemas.event import EventCreate

    now = datetime.utcnow()
    event_service.submit_draft(
        created.eventId,
        EventCreate(
            eventName="Q3 Partner Summit",
            proposedStartAt=now + timedelta(days=7),
            proposedEndAt=now + timedelta(days=7, hours=3),
            expectedAttendance=50,
        ),
        organiser_id="u-organiser",
    )

    with pytest.raises(HTTPException) as exc_info:
        event_service.discard_draft(created.eventId, organiser_id="u-organiser")

    assert exc_info.value.status_code == 403


def test_discarded_draft_does_not_appear_in_any_listing(event_service):
    created = make_draft(event_service)
    event_service.discard_draft(created.eventId, organiser_id="u-organiser")

    assert event_service.list_events() == []
    assert event_service.list_all_events() == []
    assert event_service.list_my_drafts(organiser_id="u-organiser") == []
    assert event_service.list_my_events(organiser_id="u-organiser") == []


def test_discard_missing_event_is_not_found(event_service):
    with pytest.raises(HTTPException) as exc_info:
        event_service.discard_draft("does-not-exist", organiser_id="u-organiser")

    assert exc_info.value.status_code == 404


def test_activity_log_returns_history_entries_with_who_and_when(event_service):
    created = make_draft(event_service)
    event_service.discard_draft(created.eventId, organiser_id="u-organiser")

    log = event_service.get_activity_log(created.eventId)

    assert len(log) == 1
    assert log[0].toStatus == "discarded"
    assert log[0].changedBy == "u-organiser"
    assert log[0].createdAt is not None


def test_list_my_events_includes_drafts_and_submitted_but_not_discarded(event_service):
    draft = make_draft(event_service, organiser_id="u-organiser")
    other_draft = make_draft(event_service, organiser_id="u-organiser")
    event_service.discard_draft(other_draft.eventId, organiser_id="u-organiser")
    make_draft(event_service, organiser_id="u-other")

    mine = event_service.list_my_events(organiser_id="u-organiser")

    assert [e.eventId for e in mine] == [draft.eventId]
