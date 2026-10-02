import unittest
from unittest.mock import MagicMock, patch

import httpx
from fastapi import HTTPException

from app.orchestration import clients
from tests.unit.test_event_arrangement_clients import fake_client, reply

VENUE = {
    "venueId": "v1",
    "name": "Marina Hall A",
    "capacity": 300,
    "layouts": [{"name": "Theatre", "capacity": 300}, {"name": "Classroom", "capacity": 180}],
}


class TestRegistrationClients(unittest.TestCase):
    def test_the_registration_count_comes_from_registration_service(self):
        stub, client = fake_client(reply(200, {"count": 3}))
        with stub:
            self.assertEqual(clients.current_registration_count("e1", "Bearer token"), 3)

        call = client.__enter__.return_value.request.call_args
        self.assertTrue(call.args[1].endswith("/registrations/count"))
        self.assertEqual(call.kwargs["params"], {"eventId": "e1"})

    def test_an_unanswered_count_is_a_503_naming_registrations(self):
        stub, _client = fake_client(reply(500))
        with stub, self.assertRaises(HTTPException) as ctx:
            clients.current_registration_count("e1", None)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("Registrations could not be checked", ctx.exception.detail)

    def test_registered_attendees_leaves_out_anyone_withdrawn(self):
        roster = {"attendees": [{"userId": "u5", "status": "registered"}, {"userId": "u6", "status": "withdrawn"}]}
        stub, client = fake_client(reply(200, roster))
        with stub:
            attendees = clients.registered_attendees("e1", "Bearer token")

        self.assertEqual([row["userId"] for row in attendees], ["u5"])
        self.assertEqual(client.__enter__.return_value.request.call_args.kwargs["params"], {"eventId": "e1", "includeWithdrawn": "false"})


class TestVenueCapacityClient(unittest.TestCase):
    def capacities(self, layout, venue=VENUE):
        stub, client = fake_client(reply(200, [{"bookingId": "vb-1", "venueId": "v1"}]), reply(200, venue))
        with stub:
            return clients.booked_venue_capacities("e1", layout, "Bearer token"), client

    def test_the_booked_venue_holds_its_capacity_in_the_events_layout(self):
        capacities, client = self.capacities("theatre")

        self.assertEqual(capacities, [{"venueName": "Marina Hall A", "layout": "theatre", "capacity": 300}])
        bookings_call, venue_call = client.__enter__.return_value.request.call_args_list
        self.assertEqual(bookings_call.kwargs["params"], {"eventId": "e1", "status": "approved"})
        self.assertTrue(venue_call.args[1].endswith("/venues/v1"))

    def test_without_a_layout_or_one_the_venue_lacks_the_largest_layout_applies(self):
        for layout in (None, "Banquet"):
            with self.subTest(layout=layout):
                capacities, _client = self.capacities(layout, {**VENUE, "capacity": 320})
                self.assertEqual(capacities, [{"venueName": "Marina Hall A", "layout": None, "capacity": 320}])

    def test_no_confirmed_booking_means_nothing_to_check(self):
        stub, _client = fake_client(reply(200, []))
        with stub:
            self.assertEqual(clients.booked_venue_capacities("e1", "Theatre", None), [])

    def test_an_unanswered_venue_lookup_is_a_503_naming_the_venue(self):
        stub, _client = fake_client(reply(200, [{"bookingId": "vb-1", "venueId": "v1"}]), reply(404))
        with stub, self.assertRaises(HTTPException) as ctx:
            clients.booked_venue_capacities("e1", "Theatre", None)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertIn("venue booking could not be checked", ctx.exception.detail)


class TestRecordNotification(unittest.TestCase):
    def post_answering(self, response):
        client = MagicMock()
        client.__enter__.return_value.post.return_value = response
        return patch("app.orchestration.clients.httpx.Client", MagicMock(return_value=client)), client

    def test_a_stored_notification_is_true_and_names_the_recipient(self):
        stub, client = self.post_answering(reply(201))
        with stub:
            self.assertTrue(clients.record_notification("u1", "e3", "event.registration_settings", "T", "B", "Bearer token"))

        call = client.__enter__.return_value.post.call_args
        self.assertTrue(call.args[0].endswith("/notifications/records"))
        self.assertEqual(
            call.kwargs["json"], {"userId": "u1", "eventId": "e3", "type": "event.registration_settings", "title": "T", "body": "B"}
        )

    def test_a_refused_or_unreachable_notification_is_false(self):
        stub, _client = self.post_answering(reply(403))
        with stub:
            self.assertFalse(clients.record_notification("u1", "e3", "k", "T", "B", None))
        with patch("app.orchestration.clients.httpx.Client", side_effect=httpx.ConnectError("down")):
            self.assertFalse(clients.record_notification("u1", "e3", "k", "T", "B", None))
