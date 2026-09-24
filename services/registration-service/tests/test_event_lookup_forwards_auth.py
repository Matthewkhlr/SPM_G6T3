"""Regression test for a real bug found via live-testing against real MySQL:
_event() used to call event-service without forwarding the caller's bearer
token, so event-service's own auth check rejected every request with 401,
which this code silently remapped to a misleading 404 "Event not found".
Every real registration attempt was broken until this was fixed.

This test exercises the actual HTTP call (unlike the other register() tests,
which monkeypatch _event() itself and would not have caught this) by
intercepting httpx.Client.get and asserting on the headers it was sent.
"""

import pytest

from app.services.registration_service import _event


class _FakeResponse:
    status_code = 200

    def json(self):
        return {"eventId": "e1"}


def test_event_lookup_forwards_the_bearer_token_as_the_authorization_header(monkeypatch):
    captured = {}

    def fake_get(self, url, headers=None):
        captured["url"] = url
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr("httpx.Client.get", fake_get)

    _event("e1", "Bearer some-real-token")

    assert captured["headers"] == {"Authorization": "Bearer some-real-token"}


def test_event_lookup_sends_no_auth_header_when_none_is_available(monkeypatch):
    captured = {}

    def fake_get(self, url, headers=None):
        captured["headers"] = headers
        return _FakeResponse()

    monkeypatch.setattr("httpx.Client.get", fake_get)

    _event("e1", None)

    assert captured["headers"] == {}


def test_event_lookup_raises_not_found_when_event_service_rejects_the_token(monkeypatch):
    class _Unauthorized:
        status_code = 401

        def json(self):
            return {"detail": "Invalid or expired token"}

    monkeypatch.setattr("httpx.Client.get", lambda self, url, headers=None: _Unauthorized())

    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        _event("e1", "Bearer expired-token")

    assert exc_info.value.status_code == 404
