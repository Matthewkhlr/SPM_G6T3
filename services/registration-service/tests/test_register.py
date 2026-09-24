from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

from app.models.registration_window import RegistrationWindow


def confirmed_event_payload(**overrides):
    now = datetime.utcnow()
    defaults = dict(
        status="confirmed",
        registrationEnabled=True,
        registrationOpensAt=(now - timedelta(days=1)).isoformat(),
        registrationClosesAt=(now + timedelta(days=1)).isoformat(),
        capacity=10,
    )
    defaults.update(overrides)
    return defaults


def make_window(db_session, event_id="e1", capacity=10):
    now = datetime.utcnow()
    window = RegistrationWindow(
        eventId=event_id, capacity=capacity, opensAt=now - timedelta(days=1), closesAt=now + timedelta(days=1)
    )
    db_session.add(window)
    db_session.commit()
    return window


def test_register_succeeds_when_event_is_open_and_window_exists(registration_service, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.registration_service._event", lambda event_id, authorization=None: confirmed_event_payload()
    )
    make_window(db_session)

    row = registration_service.register("e1", "Amy Wong", "amy@example.com", user_id=None)

    assert row.status == "registered"
    assert row.attendeeEmail == "amy@example.com"


def test_register_without_a_registration_window_conflicts(registration_service, monkeypatch):
    monkeypatch.setattr(
        "app.services.registration_service._event", lambda event_id, authorization=None: confirmed_event_payload()
    )

    with pytest.raises(HTTPException) as exc_info:
        registration_service.register("e-no-window", "Amy Wong", "amy@example.com", user_id=None)

    assert exc_info.value.status_code == 409


def test_register_rejects_missing_name_or_email(registration_service):
    with pytest.raises(HTTPException) as exc_info:
        registration_service.register("e1", "", "amy@example.com", user_id=None)

    assert exc_info.value.status_code == 409


def test_register_when_event_not_confirmed_conflicts(registration_service, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.registration_service._event",
        lambda event_id, authorization=None: confirmed_event_payload(status="submitted"),
    )
    make_window(db_session)

    with pytest.raises(HTTPException) as exc_info:
        registration_service.register("e1", "Amy Wong", "amy@example.com", user_id=None)

    assert exc_info.value.status_code == 409


def test_register_duplicate_email_conflicts(registration_service, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.registration_service._event", lambda event_id, authorization=None: confirmed_event_payload()
    )
    make_window(db_session)
    registration_service.register("e1", "Amy Wong", "amy@example.com", user_id=None)

    with pytest.raises(HTTPException) as exc_info:
        registration_service.register("e1", "Amy Again", "AMY@example.com", user_id=None)

    assert exc_info.value.status_code == 409


def test_list_for_event_only_returns_registered_status(registration_service, db_session, monkeypatch):
    monkeypatch.setattr(
        "app.services.registration_service._event", lambda event_id, authorization=None: confirmed_event_payload()
    )
    make_window(db_session)
    registered = registration_service.register("e1", "Amy Wong", "amy@example.com", user_id=None)
    registered.status = "withdrawn"
    db_session.commit()

    assert registration_service.list_for_event("e1") == []
