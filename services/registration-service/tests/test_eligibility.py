from datetime import datetime, timedelta

from app.services.registration_service import eligibility


def confirmed_event(**overrides):
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


def test_eligible_when_open_and_under_capacity():
    ok, reason = eligibility(confirmed_event(), registered_count=5)
    assert ok is True
    assert reason is None


def test_not_eligible_when_event_not_confirmed():
    ok, reason = eligibility(confirmed_event(status="submitted"), registered_count=0)
    assert ok is False
    assert "confirmed" in reason.lower()


def test_not_eligible_when_registration_not_enabled():
    ok, reason = eligibility(confirmed_event(registrationEnabled=False), registered_count=0)
    assert ok is False


def test_not_eligible_before_registration_opens():
    now = datetime.utcnow()
    ok, reason = eligibility(
        confirmed_event(registrationOpensAt=(now + timedelta(days=1)).isoformat()), registered_count=0
    )
    assert ok is False
    assert "opens" in reason.lower()


def test_not_eligible_after_registration_closes():
    now = datetime.utcnow()
    ok, reason = eligibility(
        confirmed_event(registrationClosesAt=(now - timedelta(hours=1)).isoformat()), registered_count=0
    )
    assert ok is False
    assert "closed" in reason.lower()


def test_not_eligible_at_capacity():
    ok, reason = eligibility(confirmed_event(capacity=5), registered_count=5)
    assert ok is False
    assert "capacity" in reason.lower()
