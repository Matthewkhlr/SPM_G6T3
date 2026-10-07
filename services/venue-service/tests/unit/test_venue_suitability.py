from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import HTTPException

from app.models.venue_unavailability import VenueUnavailability
from app.schemas.venue import EventFacts, Layout, OperatingHours, SuitabilityRequest
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create

MONDAY = datetime(2030, 1, 7)
SATURDAY = datetime(2030, 1, 12)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]


def at(hour, minute=0, day=MONDAY):
    return day + timedelta(hours=hour, minutes=minute)


class SuitabilityCase(VenueCase):
    """A weekday venue open 08:00 to 18:00 UTC with 30 minutes setup and 60
    minutes turnaround, and an event on a Monday 10:00 to 12:00 UTC for 10
    people, which on its own suits it. The event occupies the venue from 09:30
    to 13:00 (SPM-64)."""

    def setUp(self):
        super().setUp()
        self.venue = self.service.create_venue(
            venue_create(
                layouts=[Layout(name="Boardroom", capacity=20), Layout(name="Theatre", capacity=100)],
                facilities=["PA", "Projector"],
                accessibility=["Ramp", "Wheelchair accessible"],
                operatingHours=[OperatingHours(day=day, opens="08:00", closes="18:00") for day in WEEKDAYS],
            ),
            CALLER,
        )
        self.event = EventFacts(expectedAttendance=10, proposedStartAt=at(10), proposedEndAt=at(12))

    def check(self, **overrides):
        request = SuitabilityRequest(eventId="e-mine", venueId=self.venue.venueId, **overrides)
        return self.service.check_suitability(request, self.event)

    def messages(self, result, severity):
        return [reason.message for reason in result.reasons if reason.severity == severity]

    def booking(self, event_id, starts_at, ends_at, status="approved"):
        booking = self.service.create_booking(
            booking_create(self.venue.venueId, eventId=event_id, startsAt=starts_at, endsAt=ends_at),
            "u-coord",
        )
        if status == "approved":
            self.service.approve_booking(booking.bookingId, "u-venue", None)
        elif status == "rejected":
            self.service.reject_booking(booking.bookingId, "u-venue", None)
        return booking

    def unavailable(self, starts_at, ends_at, reason):
        self.db.add(
            VenueUnavailability(
                unavailabilityId=str(uuid4()),
                venueId=self.venue.venueId,
                startsAt=starts_at,
                endsAt=ends_at,
                reason=reason,
                createdBy="u-venue",
            )
        )
        self.db.commit()


class TestVerdict(SuitabilityCase):
    """AC1: suitable, suitable with warnings, or not suitable, with a reason for every point."""

    def test_an_event_that_fits_is_suitable_with_no_reasons(self):
        result = self.check()

        self.assertEqual(result.verdict, "suitable")
        self.assertEqual(result.reasons, [])
        self.assertEqual((result.eventId, result.venueId), ("e-mine", self.venue.venueId))

    def test_only_warnings_gives_suitable_with_warnings(self):
        result = self.check(expectedAttendance=19, layout="Boardroom")

        self.assertEqual(result.verdict, "suitable with warnings")
        self.assertEqual([reason.check for reason in result.reasons], ["capacity"])

    def test_any_failure_gives_not_suitable_and_lists_failures_before_warnings(self):
        # The tight-fit warning is found before the clash failure, but is listed after it.
        self.booking("e-other", at(9), at(11))

        result = self.check(expectedAttendance=19, layout="Boardroom")

        self.assertEqual(result.verdict, "not suitable")
        self.assertEqual([reason.severity for reason in result.reasons], ["failure", "warning"])
        self.assertEqual([reason.check for reason in result.reasons], ["clash", "capacity"])
        self.assertTrue(all(reason.message for reason in result.reasons))

    def test_a_retired_venue_is_not_suitable(self):
        self.service.retire_venue(self.venue.venueId, CALLER)

        result = self.check()

        self.assertEqual(result.verdict, "not suitable")
        self.assertIn("retired", self.messages(result, "failure")[0])

    def test_an_unknown_venue_is_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.check_suitability(SuitabilityRequest(eventId="e-mine", venueId="nope"), self.event)

        self.assertEqual(ctx.exception.status_code, 404)


class TestCapacity(SuitabilityCase):
    """AC2 (over capacity fails, naming both numbers) and AC6 (above about 90% warns)."""

    def test_attendance_above_the_layout_capacity_fails_and_names_both_numbers(self):
        result = self.check(expectedAttendance=21, layout="Boardroom")

        self.assertEqual(result.verdict, "not suitable")
        self.assertEqual(
            self.messages(result, "failure"),
            ["Expected attendance of 21 is more than this venue can hold in the Boardroom layout (20 people)."],
        )

    def test_attendance_equal_to_the_layout_capacity_is_not_a_failure(self):
        result = self.check(expectedAttendance=20, layout="Boardroom")

        self.assertEqual(result.verdict, "suitable with warnings")

    def test_without_a_layout_attendance_is_compared_with_the_overall_capacity(self):
        result = self.check(expectedAttendance=101)

        self.assertEqual(
            self.messages(result, "failure"),
            ["Expected attendance of 101 is more than this venue can hold (100 people)."],
        )
        self.assertEqual(self.check(expectedAttendance=100).verdict, "suitable with warnings")

    def test_exactly_ninety_percent_is_not_flagged(self):
        self.assertEqual(self.check(expectedAttendance=18, layout="Boardroom").verdict, "suitable")

    def test_just_above_ninety_percent_is_a_warning_not_a_failure(self):
        result = self.check(expectedAttendance=19, layout="Boardroom")

        self.assertEqual(result.verdict, "suitable with warnings")
        self.assertEqual(
            self.messages(result, "warning"),
            [
                "Expected attendance of 19 is above 90% of what this venue can hold in the Boardroom layout "
                "(20 people), so it will be a tight fit."
            ],
        )


class TestLayoutFacilitiesAccessibility(SuitabilityCase):
    """AC3: each missing item is its own failure, naming the item."""

    def test_an_unsupported_layout_fails_naming_it_and_skips_the_capacity_check(self):
        result = self.check(layout="Exhibition", expectedAttendance=500)

        self.assertEqual(
            self.messages(result, "failure"),
            ["This venue does not offer the Exhibition layout. Layouts offered: Boardroom, Theatre."],
        )

    def test_a_venue_with_no_layouts_fails_any_required_layout_and_says_none_are_offered(self):
        bare = self.service.create_venue(venue_create(name="Empty Room", layouts=[]), CALLER)

        result = self.service.check_suitability(
            SuitabilityRequest(eventId="e-mine", venueId=bare.venueId, layout="Theatre"), self.event
        )

        self.assertEqual(
            self.messages(result, "failure"),
            ["This venue does not offer the Theatre layout. Layouts offered: none."],
        )

    def test_layout_names_match_regardless_of_case_or_spaces(self):
        self.assertEqual(self.check(layout=" boardroom ", expectedAttendance=10).verdict, "suitable")

    def test_each_missing_facility_is_named_once(self):
        result = self.check(requiredFacilities=["pa", "Loading dock", "Stage", "loading dock ", " "])

        self.assertEqual(
            self.messages(result, "failure"),
            [
                "Required facility not available at this venue: Loading dock.",
                "Required facility not available at this venue: Stage.",
            ],
        )

    def test_a_missing_accessibility_feature_is_named(self):
        result = self.check(requiredAccessibility=["ramp", "Hearing loop"])

        self.assertEqual(
            self.messages(result, "failure"),
            ["Required accessibility feature not available at this venue: Hearing loop."],
        )


class TestClashes(SuitabilityCase):
    """AC4 (overlapping confirmed booking or unavailability fails) and AC7 (overlapping pending request warns)."""

    def test_an_overlapping_confirmed_booking_fails_naming_the_event(self):
        self.booking("e-other", at(11), at(14))

        result = self.check()

        self.assertEqual(result.verdict, "not suitable")
        self.assertEqual(
            self.messages(result, "failure"),
            [
                "This venue already has a confirmed booking for event e-other at an overlapping time "
                "(07 Jan 2030, 10:30 AM to 03:00 PM UTC, including setup and turnaround)."
            ],
        )

    def test_the_venues_setup_and_turnaround_count_towards_the_clash(self):
        # 07:00 to 09:00 is turned around until 10:00, after this event's setup begins at 09:30.
        self.booking("e-early", at(7), at(9))

        early = self.messages(self.check(), "failure")

        self.assertEqual(len(early), 1)
        self.assertIn("event e-early", early[0])

    def test_event_times_that_only_touch_can_still_clash(self):
        # 12:00 to 13:00 starts as this event ends, but its setup from 11:30 overlaps.
        self.booking("e-after", at(12), at(13))

        self.assertEqual(self.check().verdict, "not suitable")

    def test_occupied_windows_that_only_touch_do_not_clash(self):
        # Turned around by 09:30, and set up from 13:00: exactly this event's window.
        self.booking("e-before", at(7), at(8, 30))
        self.booking("e-after", at(13, 30), at(14))

        self.assertEqual(self.check().verdict, "suitable")

    def test_the_events_own_booking_and_rejected_bookings_do_not_clash(self):
        self.booking("e-mine", at(10), at(12))
        self.booking("e-other", at(10), at(12), status="rejected")

        self.assertEqual(self.check().verdict, "suitable")

    def test_a_clash_spanning_two_days_names_both_dates(self):
        self.booking("e-other", at(-2), at(11))

        self.assertIn("06 Jan 2030, 09:30 PM to 07 Jan 2030, 12:00 PM UTC", self.messages(self.check(), "failure")[0])

    def test_an_overlapping_unavailability_period_fails_naming_it(self):
        self.unavailable(at(11), at(15), "Maintenance")

        result = self.check()

        self.assertEqual(
            self.messages(result, "failure"),
            ["This venue is unavailable from 07 Jan 2030, 11:00 AM to 03:00 PM UTC (Maintenance)."],
        )

    def test_unavailability_without_a_reason_and_outside_the_event_is_handled(self):
        # Touching the occupied window (09:30 to 13:00) on either side is not a clash.
        self.unavailable(at(8), at(9, 30), "")
        self.unavailable(at(13), at(14), "")
        self.assertEqual(self.check().verdict, "suitable")

        self.unavailable(at(9), at(11), "")
        self.assertEqual(
            self.messages(self.check(), "failure"),
            ["This venue is unavailable from 07 Jan 2030, 09:00 AM to 11:00 AM UTC."],
        )

    def test_an_overlapping_pending_request_is_a_warning(self):
        self.booking("e-other", at(11), at(13), status="pending")

        result = self.check()

        self.assertEqual(result.verdict, "suitable with warnings")
        self.assertEqual([reason.check for reason in result.reasons], ["pendingRequest"])
        self.assertIn("event e-other", result.reasons[0].message)


class TestOpeningHours(SuitabilityCase):
    """AC5: a requested time outside the venue's opening hours fails. Hours are UTC."""

    def test_starting_at_opening_and_ending_at_closing_is_inside_the_hours(self):
        self.assertEqual(self.check(startsAt=at(8), endsAt=at(18)).verdict, "suitable")

    def test_starting_a_minute_before_opening_fails(self):
        result = self.check(startsAt=at(7, 59), endsAt=at(12))

        self.assertEqual(
            self.messages(result, "failure"),
            [
                "On Monday 07 Jan 2030 the event runs 07:59 AM to 12:00 PM UTC, outside this venue's opening "
                "hours of 08:00 to 18:00 UTC."
            ],
        )

    def test_ending_a_minute_after_closing_fails(self):
        self.assertEqual(self.check(startsAt=at(16), endsAt=at(18, 1)).verdict, "not suitable")

    def test_opening_hours_apply_to_the_requested_event_time_not_setup_or_turnaround(self):
        # AC5 is about the requested time: the venue's setup from 07:30 and turnaround
        # until 19:00 around an 08:00 to 18:00 event is not an opening-hours failure.
        result = self.check(startsAt=at(8), endsAt=at(18))

        self.assertEqual(result.verdict, "suitable")

    def test_a_day_the_venue_is_closed_fails(self):
        result = self.check(startsAt=at(10, day=SATURDAY), endsAt=at(12, day=SATURDAY))

        self.assertEqual(
            self.messages(result, "failure"),
            ["This venue is closed on Saturday 12 Jan 2030, so the event is outside its opening hours."],
        )

    def test_an_event_running_overnight_fails_on_both_days(self):
        result = self.check(startsAt=at(16), endsAt=at(34))

        self.assertEqual(len(self.messages(result, "failure")), 2)
        self.assertIn("Monday 07 Jan 2030", result.reasons[0].message)
        self.assertIn("Tuesday 08 Jan 2030", result.reasons[1].message)

    def test_an_event_ending_exactly_at_midnight_is_checked_on_one_day_only(self):
        result = self.check(startsAt=at(17), endsAt=at(24))

        self.assertEqual(len(result.reasons), 1)
        self.assertIn("05:00 PM to 12:00 AM UTC", result.reasons[0].message)

    def test_times_sent_with_a_timezone_are_converted_to_utc(self):
        singapore = timezone(timedelta(hours=8))
        in_hours = self.check(
            startsAt=datetime(2030, 1, 7, 18, 0, tzinfo=singapore), endsAt=datetime(2030, 1, 7, 20, 0, tzinfo=singapore)
        )
        before_opening = self.check(
            startsAt=datetime(2030, 1, 7, 9, 0, tzinfo=singapore), endsAt=datetime(2030, 1, 7, 11, 0, tzinfo=singapore)
        )

        self.assertEqual(in_hours.verdict, "suitable")
        self.assertIn("01:00 AM to 03:00 AM UTC", before_opening.reasons[0].message)


class TestSchedule(SuitabilityCase):
    def test_an_event_with_no_date_warns_that_time_checks_were_skipped(self):
        self.booking("e-other", at(10), at(12))
        self.event = EventFacts(expectedAttendance=10)

        result = self.check()

        self.assertEqual(result.verdict, "suitable with warnings")
        self.assertEqual([reason.check for reason in result.reasons], ["schedule"])

    def test_an_end_before_the_start_fails(self):
        result = self.check(startsAt=at(12), endsAt=at(10))

        self.assertEqual(self.messages(result, "failure"), ["The event's end time must be after its start time."])


class TestEventFacts(SuitabilityCase):
    """Anything the request leaves out comes from the event record."""

    def test_the_event_record_supplies_attendance_layout_and_times(self):
        self.event = EventFacts(
            expectedAttendance=21, layoutPreference="Boardroom", proposedStartAt=at(7), proposedEndAt=at(9)
        )

        checks = [reason.check for reason in self.check().reasons]

        self.assertEqual(checks, ["capacity", "openingHours"])

    def test_the_request_overrides_the_event_record(self):
        self.event = EventFacts(
            expectedAttendance=500, layoutPreference="Exhibition", proposedStartAt=at(7), proposedEndAt=at(9)
        )

        result = self.check(expectedAttendance=10, layout="", startsAt=at(10), endsAt=at(12))

        self.assertEqual(result.verdict, "suitable")
