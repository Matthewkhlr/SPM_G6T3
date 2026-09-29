import unittest
from unittest.mock import Mock, patch

import httpx
from fastapi import HTTPException

from app.orchestration import clients
from tests.unit.support import ORGANISER, TECH


def _user_client(status_code, payload):
    class _Client:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, headers=None):
            response = Mock(status_code=status_code)
            response.json.return_value = payload
            return response

    return _Client


class TestEventClients(unittest.TestCase):
    def test_registration_count_returns_the_list_length(self):
        response = Mock(status_code=200)
        response.json.return_value = [{"id": "r1"}, {"id": "r2"}]
        with patch.object(clients._registration_client, "get", return_value=response) as get:
            count = clients.registration_count("e1", "Bearer token")

        self.assertEqual(count, 2)
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_registration_count_is_zero_when_the_status_is_not_200(self):
        response = Mock(status_code=503)
        with patch.object(clients._registration_client, "get", return_value=response):
            count = clients.registration_count("e1", None)

        self.assertEqual(count, 0)

    def test_registration_count_is_zero_when_the_call_fails(self):
        with patch.object(clients._registration_client, "get", side_effect=httpx.ConnectError("down")):
            count = clients.registration_count("e1", "Bearer token")

        self.assertEqual(count, 0)

    def test_organisation_names_returns_the_id_to_name_mapping(self):
        response = Mock(status_code=200)
        response.json.return_value = [
            {"organisationId": "org-1", "name": "Apex Partners"},
            {"organisationId": "org-2", "name": "Beacon Media"},
        ]
        with patch.object(clients._user_directory_client, "get", return_value=response) as get:
            names = clients.organisation_names("Bearer token")

        self.assertEqual(names, {"org-1": "Apex Partners", "org-2": "Beacon Media"})
        self.assertEqual(get.call_args.kwargs["headers"], {"Authorization": "Bearer token"})

    def test_organisation_names_is_empty_when_the_status_is_not_200(self):
        response = Mock(status_code=503)
        with patch.object(clients._user_directory_client, "get", return_value=response):
            names = clients.organisation_names(None)

        self.assertEqual(names, {})

    def test_current_organiser_rejects_a_missing_token(self):
        with self.assertRaises(HTTPException) as ctx:
            clients.current_organiser(None)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_organiser_rejects_an_unreachable_user_service(self):
        with patch("app.orchestration.clients.httpx.Client", side_effect=httpx.ConnectError("down")):
            with self.assertRaises(HTTPException) as ctx:
                clients.current_organiser("Bearer token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_organiser_rejects_a_non_200_response(self):
        with patch("app.orchestration.clients.httpx.Client", _user_client(503, {})):
            with self.assertRaises(HTTPException) as ctx:
                clients.current_organiser("Bearer token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_organiser_rejects_a_non_organiser(self):
        with patch("app.orchestration.clients.httpx.Client", _user_client(200, {"role": "attendee", "userId": "u"})):
            with self.assertRaises(HTTPException) as ctx:
                clients.current_organiser("Bearer token")

        self.assertEqual(ctx.exception.status_code, 403)

    def test_current_organiser_returns_the_user(self):
        with patch("app.orchestration.clients.httpx.Client", _user_client(200, ORGANISER)):
            user = clients.current_organiser("Bearer token")

        self.assertEqual(user["userId"], "org-1")

    def test_current_technical_support_rejects_a_missing_token(self):
        with self.assertRaises(HTTPException) as ctx:
            clients.current_technical_support(None)

        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_technical_support_rejects_an_unreachable_user_service(self):
        with patch("app.orchestration.clients.httpx.Client", side_effect=httpx.ConnectError("down")):
            with self.assertRaises(HTTPException) as ctx:
                clients.current_technical_support("Bearer token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_technical_support_rejects_a_non_200_response(self):
        with patch("app.orchestration.clients.httpx.Client", _user_client(404, {})):
            with self.assertRaises(HTTPException) as ctx:
                clients.current_technical_support("Bearer token")

        self.assertEqual(ctx.exception.status_code, 401)

    def test_current_technical_support_rejects_another_role(self):
        with patch("app.orchestration.clients.httpx.Client", _user_client(200, ORGANISER)):
            with self.assertRaises(HTTPException) as ctx:
                clients.current_technical_support("Bearer token")

        self.assertEqual(ctx.exception.status_code, 403)

    def test_current_technical_support_returns_the_user(self):
        with patch("app.orchestration.clients.httpx.Client", _user_client(200, TECH)):
            user = clients.current_technical_support("Bearer token")

        self.assertEqual(user["role"], "techsupport")
