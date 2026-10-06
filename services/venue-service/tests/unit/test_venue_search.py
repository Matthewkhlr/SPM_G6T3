"""SPM-61: search and filter venues against an event's requirements."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_unavailability import VenueUnavailability
from app.schemas.venue import Layout, OperatingHours
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

MONDAY = datetime(2030, 1, 7)
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def at(hour, minute=0, day=MONDAY):
    return day + timedelta(hours=hour, minutes=minute)


class SearchCase(VenueCase):
    """Marina Hall A: HarbourFront, open every day 08:00 to 20:00 UTC, Theatre
    for 100 and Classroom for 40, 30 minutes setup and 60 minutes turnaround.
    The period searched is Monday 10:00 to 12:00 UTC, so the hall is occupied
    09:30 to 13:00."""

    def setUp(self):
        super().setUp()
        self.hall = self.add_venue(
            name="Marina Hall A",
            facilities=["PA system", "Stage"],
            accessibility=["Wheelchair accessible"],
        )

    def add_venue(self, **overrides):
        data = dict(
            operatingHours=[OperatingHours(day=day, opens="08:00", closes="20:00") for day in ALL_DAYS],
            setupMinutes=30,
            turnaroundMinutes=60,
        )
        data.update(overrides)
        return self.service.create_venue(venue_create(**data), CALLER)

    def search(self, starts_at=at(10), ends_at=at(12), **filters):
        return self.service.search_venues(starts_at=starts_at, ends_at=ends_at, **filters)

    def names(self, **kwargs):
        return [row.name for row in self.search(**kwargs)]

    def book(self, starts_at, ends_at, status="approved", event_id="e-other", venue=None):
        booking = self.service.create_booking(
            booking_create(
                (venue or self.hall).venueId,
                eventId=event_id,
                startsAt=starts_at,
                endsAt=ends_at,
                setupStartsAt=starts_at,
                teardownEndsAt=ends_at,
            ),
            "u-coord",
        )
        if status == "approved":
            self.service.approve_booking(booking.bookingId, "u-venue", None)
        elif status == "rejected":
            self.service.reject_booking(booking.bookingId, "u-venue", "Closed that day")
        return booking

    def block(self, starts_at, ends_at):
        self.db.add(
            VenueUnavailability(
                unavailabilityId=f"u-{starts_at:%H%M}-{ends_at:%H%M}",
                venueId=self.hall.venueId,
                startsAt=starts_at,
                endsAt=ends_at,
                reason="Maintenance",
                createdBy="u-venue",
            )
        )
        self.db.commit()


class TestCapacityAndLayout(SearchCase):
    """AC5 and AC8: capacity in the required layout, and the headroom over the attendance."""

    def test_each_result_shows_its_capacity_in_the_layout_and_the_headroom(self):
        [row] = self.search(layout="Theatre", min_capacity=80)

        self.assertEqual((row.layout, row.layoutCapacity, row.headroom), ("Theatre", 100, 20))
        self.assertEqual((row.setupMinutes, row.turnaroundMinutes), (30, 60))

    def test_capacity_exactly_equal_to_the_attendance_fits_and_one_more_does_not(self):
        [row] = self.search(layout="Classroom", min_capacity=40)

        self.assertEqual((row.layoutCapacity, row.headroom), (40, 0))
        self.assertEqual(row.capacity, 100)
        self.assertEqual(self.names(layout="Classroom", min_capacity=41), [])

    def test_a_layout_the_venue_does_not_offer_excludes_it(self):
        self.assertEqual(self.names(layout="Banquet"), [])

    def test_the_layout_is_matched_whatever_its_case_or_spacing(self):
        self.assertEqual(self.search(layout="  theatre ")[0].layout, "theatre")

    def test_without_a_layout_the_venues_overall_capacity_is_used(self):
        [row] = self.search(min_capacity=90)

        self.assertIsNone(row.layout)
        self.assertEqual((row.layoutCapacity, row.headroom), (100, 10))
        self.assertIsNone(self.search(layout="  ")[0].layout)


class TestFilters(SearchCase):
    """AC2 and AC6: location, facilities and accessibility."""

    def test_location_matches_part_of_the_venues_location_ignoring_case(self):
        self.add_venue(name="Skyline Boardroom", location="One Raffles Place")

        self.assertEqual(self.names(location="harbourfront"), ["Marina Hall A"])
        self.assertEqual(self.names(location="Raffles"), ["Skyline Boardroom"])

    def test_a_missing_required_facility_excludes_the_venue(self):
        self.assertEqual(self.names(facilities=["PA system", "Stage"]), ["Marina Hall A"])
        self.assertEqual(self.names(facilities=["pa SYSTEM"]), ["Marina Hall A"])
        self.assertEqual(self.names(facilities=["PA system", "Loading dock"]), [])

    def test_a_missing_required_accessibility_feature_excludes_the_venue(self):
        self.assertEqual(self.names(accessibility=["Wheelchair accessible"]), ["Marina Hall A"])
        self.assertEqual(self.names(accessibility=["Hearing loop"]), [])

    def test_blank_requirements_are_ignored(self):
        self.assertEqual(self.names(facilities=[""], accessibility=["  "]), ["Marina Hall A"])

    def test_retired_venues_never_appear(self):
        self.service.retire_venue(self.hall.venueId, CALLER)

        self.assertEqual(self.names(), [])

    def test_results_are_in_name_order(self):
        self.add_venue(name="Zenith Hall")
        self.add_venue(name="atrium")

        self.assertEqual(self.names(), ["atrium", "Marina Hall A", "Zenith Hall"])

    def test_search_filters_by_capacity_and_facility(self):
        """Moved from tests/upcoming now that search exists."""
        self.add_venue(
            name="Boardroom",
            location="City",
            facilities=["Whiteboard"],
            layouts=[Layout(name="Boardroom", capacity=12)],
            setupMinutes=10,
            turnaroundMinutes=15,
        )

        matches = self.service.search_venues(min_capacity=80, facilities=["PA system"])

        self.assertEqual([row.name for row in matches], ["Marina Hall A"])


class TestOpeningHours(SearchCase):
    """AC7: a requested time outside the opening hours for that day excludes the venue."""

    def test_a_time_inside_the_opening_hours_fits_including_the_exact_opening_and_closing(self):
        self.assertEqual(self.names(starts_at=at(8), ends_at=at(20)), ["Marina Hall A"])

    def test_starting_before_opening_or_ending_after_closing_excludes_the_venue(self):
        self.assertEqual(self.names(starts_at=at(7, 59), ends_at=at(10)), [])
        self.assertEqual(self.names(starts_at=at(18), ends_at=at(20, 1)), [])

    def test_a_day_the_venue_is_closed_excludes_it(self):
        self.add_venue(name="Tuesday Room", operatingHours=[OperatingHours(day="Tue", opens="08:00", closes="20:00")])

        self.assertEqual(self.names(), ["Marina Hall A"])


class TestBookingsAndUnavailability(SearchCase):
    """AC3: a confirmed booking or unavailability overlapping the period, once the
    venue's setup and turnaround are added, excludes the venue."""

    def test_an_overlapping_confirmed_booking_excludes_the_venue(self):
        self.book(at(11), at(13))

        self.assertEqual(self.names(), [])

    def test_event_times_that_do_not_overlap_still_clash_inside_setup_and_turnaround(self):
        # The booking's 13:00 to 14:00 needs the hall from 12:30; this search needs it until 13:00.
        self.book(at(13), at(14))

        self.assertEqual(self.names(), [])

    def test_occupied_windows_that_only_touch_do_not_clash(self):
        # 13:30 to 14:00 occupies the hall from 13:00, exactly when this search's turnaround ends.
        self.book(at(13, 30), at(14))
        # 07:00 to 08:30 occupies the hall until 09:30, exactly when this search's setup begins.
        self.book(at(7), at(8, 30))

        self.assertEqual(self.names(), ["Marina Hall A"])

    def test_bookings_that_are_rejected_or_belong_to_the_searching_event_do_not_count(self):
        self.book(at(10), at(12), status="rejected")
        self.book(at(10), at(12), event_id="e-mine")

        self.assertEqual(self.names(exclude_event_id="e-mine"), ["Marina Hall A"])
        self.assertEqual(self.names(), [])

    def test_a_booking_on_another_venue_does_not_count(self):
        other = self.add_venue(name="Atrium")
        self.book(at(10), at(12), venue=other)

        self.assertEqual(self.names(), ["Marina Hall A"])

    def test_unavailability_overlapping_the_setup_time_excludes_the_venue(self):
        self.block(at(9), at(9, 45))

        self.assertEqual(self.names(), [])

    def test_unavailability_overlapping_the_turnaround_time_excludes_the_venue(self):
        self.block(at(12, 30), at(14))

        self.assertEqual(self.names(), [])

    def test_unavailability_that_only_touches_the_occupied_window_does_not_exclude_it(self):
        self.block(at(8), at(9, 30))
        self.block(at(13), at(15))

        self.assertEqual(self.names(), ["Marina Hall A"])


class TestContested(SearchCase):
    """AC9: a pending request does not exclude the venue; it marks it contested."""

    def test_an_overlapping_pending_request_keeps_the_venue_and_marks_it_contested(self):
        self.book(at(11), at(12), status="pending")

        [row] = self.search()

        self.assertTrue(row.contested)

    def test_rejected_and_withdrawn_requests_neither_exclude_nor_contest(self):
        self.book(at(10), at(12), status="rejected")
        withdrawn = self.book(at(10), at(12), status="pending", event_id="e-withdrawn")
        self.service.withdraw_booking(withdrawn.bookingId, {"userId": "u-coord"}, "u-coord")

        [row] = self.search()

        self.assertFalse(row.contested)

    def test_a_venue_with_no_overlapping_request_is_not_contested(self):
        self.book(at(16), at(17), status="pending")

        self.assertFalse(self.search()[0].contested)

    def test_a_confirmed_booking_still_excludes_even_with_a_pending_request(self):
        self.book(at(10), at(11), status="pending")
        self.book(at(11), at(12))

        self.assertEqual(self.names(), [])


class TestPeriod(SearchCase):
    """AC2: the date and time range is optional, but must make sense when given."""

    def test_without_a_period_bookings_and_opening_hours_are_not_checked(self):
        self.book(at(10), at(12))
        self.book(at(10), at(12), status="pending", event_id="e-pending")

        [row] = self.search(starts_at=None, ends_at=None)

        self.assertFalse(row.contested)

    def test_a_start_without_an_end_or_an_end_without_a_start_is_refused(self):
        for starts_at, ends_at in ((at(10), None), (None, at(12))):
            with self.subTest(starts_at=starts_at, ends_at=ends_at), self.assertRaises(HTTPException) as ctx:
                self.search(starts_at=starts_at, ends_at=ends_at)
            self.assertEqual(ctx.exception.status_code, 422)
            self.assertEqual(
                ctx.exception.detail, "Give both a start and an end time to search a period, or leave both out."
            )

    def test_an_end_at_or_before_the_start_is_refused(self):
        for ends_at in (at(10), at(9)):
            with self.subTest(ends_at=ends_at), self.assertRaises(HTTPException) as ctx:
                self.search(starts_at=at(10), ends_at=ends_at)
            self.assertEqual(ctx.exception.detail, "The end time must be after the start time.")

    def test_times_with_a_timezone_are_read_as_utc(self):
        self.book(at(11), at(12))
        plus_eight = timezone(timedelta(hours=8))

        self.assertEqual(
            self.names(starts_at=at(18).replace(tzinfo=plus_eight), ends_at=at(20).replace(tzinfo=plus_eight)), []
        )


class TestSearchRoute(SearchCase):
    def setUp(self):
        super().setUp()
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def get(self, role="coordinator", query=""):
        with signed_in_as(role):
            return self.client.get(f"/venues/search{query}", headers=HEADERS)

    def test_coordinators_get_the_shortlist_with_every_filter_passed_through(self):
        self.book(at(10), at(12), event_id="e-mine")
        query = (
            "?startsAt=2030-01-07T10:00:00Z&endsAt=2030-01-07T12:00:00Z&minCapacity=60&location=Harbour"
            "&layout=Theatre&facility=PA%20system&facility=Stage&accessibility=Wheelchair%20accessible&eventId=e-mine"
        )

        response = self.get(query=query)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            [
                {
                    "venueId": self.hall.venueId,
                    "code": "MH-A",
                    "name": "Marina Hall A",
                    "location": "HarbourFront",
                    "capacity": 100,
                    "layout": "Theatre",
                    "layoutCapacity": 100,
                    "headroom": 40,
                    "setupMinutes": 30,
                    "turnaroundMinutes": 60,
                    "contested": False,
                }
            ],
        )
        self.assertEqual(self.get(query="?facility=PA%20system&facility=Loading%20dock").json(), [])

    def test_venue_staff_can_search_too(self):
        self.assertEqual(self.get(role="venue").status_code, 200)

    def test_other_roles_are_refused(self):
        for role in ("techsupport", "organiser", "attendee"):
            with self.subTest(role=role):
                self.assertEqual(self.get(role=role).status_code, 403)

    def test_invalid_input_is_refused_in_plain_words(self):
        self.assertEqual(self.get(query="?minCapacity=-1").status_code, 422)
        refused = self.get(query="?startsAt=2030-01-07T10:00:00Z")
        self.assertEqual(refused.status_code, 422)
        self.assertIn("Give both a start and an end time", refused.json()["detail"])

    def test_search_is_not_mistaken_for_a_venue_id(self):
        with patch("app.routers.venue.VenueService.get_venue") as get_venue:
            self.get()
        get_venue.assert_not_called()
