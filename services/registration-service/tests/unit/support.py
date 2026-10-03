from datetime import datetime, timedelta

from app.models.registration_window import RegistrationWindow


def confirmed_event(**overrides):
    now = datetime.utcnow()
    payload = dict(
        status="confirmed",
        registrationEnabled=True,
        registrationOpensAt=(now - timedelta(days=1)).isoformat(),
        registrationClosesAt=(now + timedelta(days=1)).isoformat(),
        capacity=10,
    )
    payload.update(overrides)
    return payload


def make_window(db, event_id="e1", capacity=10):
    now = datetime.utcnow()
    window = RegistrationWindow(
        eventId=event_id,
        capacity=capacity,
        opensAt=now - timedelta(days=1),
        closesAt=now + timedelta(days=1),
    )
    db.add(window)
    db.commit()
    return window


class FakeResponse:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {"eventId": "e1"}

    def json(self):
        return self._payload


class FakeEventClient:
    response = FakeResponse(200)
    error = None
    captured = {}

    def __init__(self, timeout):
        self.timeout = timeout

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        FakeEventClient.captured = {"url": url, "headers": headers}
        if FakeEventClient.error:
            raise FakeEventClient.error
        return FakeEventClient.response
