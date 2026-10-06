from datetime import datetime, timedelta

from fastapi import HTTPException

from app.schemas.venue import EventFacts, Layout, OperatingHours, VenueBookingCreate, VenueBookingOut
from tests.unit.support import CALLER, COORDINATOR, VenueCase, booking_create, venue_create

MONDAY = datetime(2030, 1, 7)
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
OTHER_COORDINATOR = {"userId": "u-other", "userName": "Cara", "role": "coordinator"}


def at(hour, day=MONDAY):
    return day + timedelta(hours=hour)


class BookingRequestCase(VenueCase):
    """A weekday venue open 08:00 to 18:00 UTC, and an approved event on a
    Monday 10:00 to 12:00 UTC for 10 people in a Theatre layout, assigned to
    the test coordinator. On its own, it suits the venue with no warnings."""

    def setUp(self):
        super().setUp()
        self.venue = self.venue_named("Marina Hall A")
        self.event = EventFacts(
            eventName="AI Summit",
            status="approved",
            coordinatorId=COORDINATOR["userId"],
            organisationId="org-1",
            organisationName="Apex Partners",
            expectedAttendance=10,
            layoutPreference="Theatre",
            accessibilityNeeds="Wheelchair access required.",
            venueRequirements="Stage and PA system.",
            proposedStartAt=at(10),
            proposedEndAt=at(12),
        )

    def venue_named(self, name):
        return self.service.create_venue(
            venue_create(
                name=name,
                layouts=[Layout(name="Theatre", capacity=100), Layout(name="Boardroom", capacity=20)],
                operatingHours=[OperatingHours(day=day, opens="08:00", closes="18:00") for day in WEEKDAYS],
            ),
            CALLER,
        )

    def request(self, caller=COORDINATOR, event=None, **overrides):
        data = dict(
            venueId=self.venue.venueId,
            eventId="e-mine",
            startsAt=at(10),
            endsAt=at(12),
            setupStartsAt=at(10),
            teardownEndsAt=at(12),
            coordinatorNotes="Please keep the side entrance unlocked.",
        )
        data.update(overrides)
        return self.service.request_booking(VenueBookingCreate(**data), caller, event or self.event)

    def withdraw(self, booking_id, caller=COORDINATOR, assigned=COORDINATOR["userId"]):
        """`assigned` is the event's coordinator at the moment of withdrawing."""
        return self.service.withdraw_booking(booking_id, caller, assigned)

    def refused(self, status_code, **kwargs):
        with self.assertRaises(HTTPException) as ctx:
            self.request(**kwargs)
        self.assertEqual(ctx.exception.status_code, status_code)
        return ctx.exception.detail

    def event_with(self, **changes):
        return self.event.model_copy(update=changes)


class TestWhoCanRequest(BookingRequestCase):
    """AC1: the assigned coordinator, for an event in Planning (approved or planning)."""

    def test_the_assigned_coordinator_can_request_a_venue_for_an_approved_event(self):
        booking = self.request()

        self.assertEqual(booking.status, "pending")
        self.assertEqual(booking.requestedBy, COORDINATOR["userId"])
        self.assertEqual(booking.eventId, "e-mine")

    def test_an_event_in_planning_status_can_also_request_a_venue(self):
        self.assertEqual(self.request(event=self.event_with(status="planning")).status, "pending")

    def test_a_coordinator_not_assigned_to_the_event_is_refused_and_nothing_is_saved(self):
        detail = self.refused(403, caller=OTHER_COORDINATOR)

        self.assertEqual(detail, "Only the coordinator assigned to this event can request a venue for it.")
        self.assertEqual(self.service.list_bookings(), [])

    def test_an_event_with_no_coordinator_yet_is_refused(self):
        self.refused(403, event=self.event_with(coordinatorId=None))

    def test_events_not_yet_in_planning_or_past_it_are_refused(self):
        for status in ("draft", "submitted", "rejected", "confirmed", "completed", "cancelled"):
            with self.subTest(status=status):
                detail = self.refused(409, event=self.event_with(status=status))
                self.assertEqual(
                    detail,
                    "A venue can only be requested once the event has been approved for planning. "
                    f"This event is currently {status}.",
                )
        self.assertIn("not yet approved", self.refused(409, event=self.event_with(status="")))
        self.assertEqual(self.service.list_bookings(), [])


class TestWhatTheRequestCarries(BookingRequestCase):
    """AC2: event name, client organisation, date and times, attendance, layout,
    accessibility needs, required facilities, and the coordinator's notes."""

    def test_the_request_carries_the_event_facts_and_the_coordinators_notes(self):
        booking = self.request()

        self.assertEqual(
            booking.eventSnapshot,
            {
                "eventName": "AI Summit",
                "clientOrganisation": "Apex Partners",
                "startsAt": "2030-01-07T10:00:00",
                "endsAt": "2030-01-07T12:00:00",
                "expectedAttendance": 10,
                "layout": "Theatre",
                "accessibilityNeeds": "Wheelchair access required.",
                "requiredFacilities": "Stage and PA system.",
            },
        )
        self.assertEqual(booking.coordinatorNotes, "Please keep the side entrance unlocked.")
        self.assertEqual(self.service.get_booking(booking.bookingId), booking)

    def test_missing_event_facts_are_carried_as_empty_rather_than_invented(self):
        event = self.event_with(layoutPreference=None, proposedStartAt=None, proposedEndAt=None)

        booking = self.request(event=event, acknowledgeWarnings=True)

        self.assertIsNone(booking.eventSnapshot["startsAt"])
        self.assertIsNone(booking.eventSnapshot["endsAt"])
        self.assertEqual(booking.eventSnapshot["layout"], "")

    def test_when_the_organisation_name_could_not_be_loaded_its_id_still_names_the_client(self):
        without_name = self.request(event=self.event_with(organisationName=None))
        self.withdraw(without_name.bookingId)
        without_client = self.request(event=self.event_with(organisationName=None, organisationId=None))

        self.assertEqual(without_name.eventSnapshot["clientOrganisation"], "org-1")
        self.assertEqual(without_client.eventSnapshot["clientOrganisation"], "")

    def test_an_unknown_booking_is_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_booking("nope")
        self.assertEqual(ctx.exception.status_code, 404)


class TestSuitabilityGate(BookingRequestCase):
    """AC3 (failures block and are shown) and AC4 (warnings need acknowledging and travel with the request)."""

    def test_a_venue_that_fails_the_check_cannot_be_requested_and_the_failures_are_shown(self):
        detail = self.refused(409, event=self.event_with(expectedAttendance=150))

        self.assertEqual(
            detail,
            "This venue is not suitable for this event, so the request cannot be sent. "
            "Expected attendance of 150 is more than this venue can hold in the Theatre layout (100 people).",
        )
        self.assertEqual(self.service.list_bookings(), [])

    def test_acknowledging_does_not_let_a_failing_venue_through(self):
        self.refused(409, event=self.event_with(expectedAttendance=150), acknowledgeWarnings=True)

    def test_a_venue_with_warnings_needs_the_coordinator_to_acknowledge_them_first(self):
        detail = self.refused(409, event=self.event_with(expectedAttendance=95))

        self.assertTrue(detail.startswith("This venue has warnings. Please read them and confirm before sending"))
        self.assertIn("Expected attendance of 95 is above 90%", detail)
        self.assertEqual(self.service.list_bookings(), [])

    def test_acknowledged_warnings_are_sent_and_carried_to_venue_staff_with_the_request(self):
        booking = self.request(event=self.event_with(expectedAttendance=95), acknowledgeWarnings=True)

        self.assertEqual(
            booking.warnings,
            [
                "Expected attendance of 95 is above 90% of what this venue can hold in the Theatre layout "
                "(100 people), so it will be a tight fit."
            ],
        )
        self.assertEqual(self.service.get_booking(booking.bookingId).warnings, booking.warnings)

    def test_a_venue_with_no_warnings_needs_no_acknowledgement_and_carries_none(self):
        self.assertEqual(self.request().warnings, [])


class TestPendingQueueAndNotifications(BookingRequestCase):
    """AC5: the request lands in Venue Staff's pending queue, and they are told about it."""

    def test_a_submitted_request_is_in_the_pending_queue_oldest_first(self):
        first = self.request()
        second = self.request(eventId="e-second", venueId=self.venue_named("Riverside Room").venueId)

        queue = self.service.list_bookings(status="pending")

        self.assertEqual([row.bookingId for row in queue], [first.bookingId, second.bookingId])

    def test_the_notice_to_venue_staff_names_the_event_venue_and_time(self):
        subject, body = self.service.venue_staff_notice(self.request(), "requested")

        self.assertEqual(subject, "New venue request: AI Summit at Marina Hall A")
        self.assertEqual(
            body,
            "A coordinator has requested Marina Hall A for AI Summit, 07 Jan 2030, 10:00 AM to 07 Jan 2030, "
            "12:00 PM UTC. It is waiting in your pending queue.",
        )

    def test_a_request_without_event_facts_is_still_described(self):
        raw = self.service.create_booking(booking_create(self.venue.venueId, eventId="e9"), "u-coord")
        unknown_venue = VenueBookingOut(**{**raw.model_dump(), "venueId": "gone"})

        self.assertEqual(self.service.venue_staff_notice(raw, "requested")[0], "New venue request: event e9 at Marina Hall A")
        self.assertIn("gone", self.service.venue_staff_notice(unknown_venue, "requested")[0])


class TestPendingDoesNotBlockOthers(BookingRequestCase):
    """AC6: a pending request is a warning to other events, never a block."""

    def test_another_event_can_still_request_the_same_venue_and_time(self):
        self.request()
        other = self.event_with(eventName="Board Meeting")

        warned = self.refused(409, event=other, eventId="e-other")
        booking = self.request(event=other, eventId="e-other", acknowledgeWarnings=True)

        self.assertIn("waiting for a decision", warned)
        self.assertEqual(booking.status, "pending")
        self.assertEqual(len(self.service.list_bookings(status="pending")), 2)

    def test_warnings_and_clashes_name_the_other_event_in_plain_words_not_by_its_id(self):
        first = self.request()
        other = self.event_with(eventName="Board Meeting")

        warned = self.refused(409, event=other, eventId="e-other")
        self.service.approve_booking(first.bookingId, "u-venue", None)
        clashed = self.refused(409, event=other, eventId="e-other")

        self.assertIn('Another booking request for this venue ("AI Summit") is waiting', warned)
        self.assertIn('already has a confirmed booking for "AI Summit" at an overlapping time', clashed)
        self.assertNotIn("e-mine", warned + clashed)


class TestSeveralVenuesPerEvent(BookingRequestCase):
    """SPM-114: one event can use several venues at the same time."""

    def test_an_event_in_planning_can_hold_several_venues_at_once(self):
        first = self.request()
        second = self.request(venueId=self.venue_named("Riverside Room").venueId)

        rows = self.service.list_bookings(event_id="e-mine")

        self.assertEqual({row.bookingId for row in rows}, {first.bookingId, second.bookingId})
        self.assertTrue(all(row.eventId == "e-mine" and row.status == "pending" for row in rows))

    def test_the_same_venue_cannot_be_requested_again_while_that_booking_is_still_live(self):
        booking = self.request()

        pending = self.refused(409)

        self.service.approve_booking(booking.bookingId, "u-venue", None)
        approved = self.refused(409)

        self.assertIn("already has a pending booking for Marina Hall A", pending)
        self.assertIn("already has an approved booking for Marina Hall A", approved)
        self.assertEqual(len(self.service.list_bookings(event_id="e-mine")), 1)

    def test_a_venue_can_be_requested_again_after_withdraw_reject_or_cancel(self):
        withdrawn = self.request()
        self.withdraw(withdrawn.bookingId)
        after_withdraw = self.request()
        self.service.reject_booking(after_withdraw.bookingId, "u-venue", "Closed that day")
        approved = self.request()
        self.service.approve_booking(approved.bookingId, "u-venue", None)
        self.service.cancel_booking(approved.bookingId, COORDINATOR, COORDINATOR["userId"])

        once_more = self.request()

        self.assertEqual(once_more.status, "pending")


class TestOneBookingCanBeReleased(BookingRequestCase):
    """SPM-114: withdrawing, rejecting, or cancelling one booking leaves the others."""

    def test_releasing_one_booking_leaves_the_event_s_other_bookings(self):
        pending = self.request()
        still_pending = self.request(venueId=self.venue_named("Riverside Room").venueId)
        self.withdraw(pending.bookingId)
        self.assertEqual(self.service.get_booking(still_pending.bookingId).status, "pending")

        self.service.reject_booking(still_pending.bookingId, "u-venue", "Closed that day")
        approved = self.request(venueId=self.venue_named("Harbour Room").venueId)
        kept = self.request(venueId=self.venue_named("Garden Room").venueId)
        self.service.approve_booking(approved.bookingId, "u-venue", None)

        cancelled = self.service.cancel_booking(approved.bookingId, COORDINATOR, COORDINATOR["userId"])

        self.assertEqual(cancelled.status, "cancelled")
        self.assertEqual(self.service.get_booking(kept.bookingId).status, "pending")
        self.assertEqual(self.service.get_booking(still_pending.bookingId).status, "rejected")

    def test_only_an_approved_booking_can_be_cancelled_by_the_assigned_coordinator_or_venue_staff(self):
        booking = self.request()

        with self.assertRaises(HTTPException) as pending:
            self.service.cancel_booking(booking.bookingId, COORDINATOR, COORDINATOR["userId"])
        self.assertEqual(pending.exception.status_code, 409)
        self.assertIn("already pending", pending.exception.detail)

        with self.assertRaises(HTTPException) as other:
            self.service.cancel_booking(booking.bookingId, OTHER_COORDINATOR, COORDINATOR["userId"])
        self.assertEqual(other.exception.status_code, 403)

        self.service.approve_booking(booking.bookingId, "u-venue", None)
        by_staff = self.service.cancel_booking(booking.bookingId, CALLER, None)

        self.assertEqual(by_staff.status, "cancelled")
        subject, body = self.service.venue_staff_notice(by_staff, "cancelled")
        self.assertEqual(subject, "Venue booking cancelled: AI Summit at Marina Hall A")
        self.assertIn("The venue is free for that time.", body)


class TestReleaseEveryBooking(BookingRequestCase):
    """SPM-114: cancelling the event frees every open venue booking for it."""

    def test_releasing_an_event_cancels_open_bookings_and_leaves_closed_ones(self):
        pending = self.request()
        approved = self.request(venueId=self.venue_named("Riverside Room").venueId)
        self.service.approve_booking(approved.bookingId, "u-venue", None)
        rejected = self.request(venueId=self.venue_named("Harbour Room").venueId)
        self.service.reject_booking(rejected.bookingId, "u-venue", "Closed that day")
        withdrawn = self.request(venueId=self.venue_named("Garden Room").venueId)
        self.withdraw(withdrawn.bookingId)

        released = self.service.release_event_bookings("e-mine")

        self.assertEqual({row.bookingId for row in released}, {pending.bookingId, approved.bookingId})
        self.assertTrue(all(row.status == "cancelled" for row in released))
        self.assertEqual(self.service.get_booking(rejected.bookingId).status, "rejected")
        self.assertEqual(self.service.get_booking(withdrawn.bookingId).status, "withdrawn")
        self.assertEqual(self.service.release_event_bookings("e-mine"), [])

    def test_arrangements_are_complete_only_when_every_requested_venue_is_approved(self):
        self.assertFalse(self.service.arrangements_complete("e-mine"))
        first = self.request()
        second = self.request(venueId=self.venue_named("Riverside Room").venueId)
        self.assertFalse(self.service.arrangements_complete("e-mine"))

        self.service.approve_booking(first.bookingId, "u-venue", None)
        self.assertFalse(self.service.arrangements_complete("e-mine"))
        self.service.approve_booking(second.bookingId, "u-venue", None)
        self.assertTrue(self.service.arrangements_complete("e-mine"))

        self.service.cancel_booking(second.bookingId, CALLER, None)
        self.assertTrue(self.service.arrangements_complete("e-mine"))
        self.service.cancel_booking(first.bookingId, CALLER, None)
        self.assertFalse(self.service.arrangements_complete("e-mine"))


class TestWithdraw(BookingRequestCase):
    """AC8: the coordinator withdraws their own pending request; it stops counting anywhere."""

    def test_the_coordinator_can_withdraw_their_own_pending_request(self):
        booking = self.request()

        withdrawn = self.withdraw(booking.bookingId)

        self.assertEqual(withdrawn.status, "withdrawn")
        self.assertEqual(self.service.list_bookings(status="pending"), [])

    def test_a_withdrawn_request_no_longer_warns_other_events(self):
        booking = self.request()
        self.withdraw(booking.bookingId)

        other = self.request(event=self.event_with(eventName="Board Meeting"), eventId="e-other")

        self.assertEqual(other.warnings, [])

    def test_a_coordinator_not_assigned_to_the_event_cannot_withdraw_its_request(self):
        booking = self.request()

        with self.assertRaises(HTTPException) as ctx:
            self.withdraw(booking.bookingId, caller=OTHER_COORDINATOR)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(
            ctx.exception.detail, "Only the coordinator assigned to this event can withdraw its venue request."
        )
        self.assertEqual(self.service.get_booking(booking.bookingId).status, "pending")

    def test_after_reassignment_the_new_coordinator_can_withdraw_and_the_previous_one_cannot(self):
        """SPM-46 AC3: the request was sent by the previous coordinator."""
        booking = self.request()

        with self.assertRaises(HTTPException) as ctx:
            self.withdraw(booking.bookingId, caller=COORDINATOR, assigned=OTHER_COORDINATOR["userId"])
        self.assertEqual(ctx.exception.status_code, 403)

        withdrawn = self.withdraw(booking.bookingId, caller=OTHER_COORDINATOR, assigned=OTHER_COORDINATOR["userId"])
        self.assertEqual(withdrawn.status, "withdrawn")

    def test_nobody_can_withdraw_while_the_event_has_no_coordinator(self):
        booking = self.request()

        with self.assertRaises(HTTPException) as ctx:
            self.withdraw(booking.bookingId, assigned=None)

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(self.service.get_booking(booking.bookingId).status, "pending")

    def test_only_a_pending_request_can_be_withdrawn(self):
        booking = self.request()
        self.service.approve_booking(booking.bookingId, "u-venue", None)

        with self.assertRaises(HTTPException) as ctx:
            self.withdraw(booking.bookingId)

        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(
            ctx.exception.detail, "Only a pending request can be withdrawn. This request is already approved."
        )

    def test_venue_staff_cannot_decide_on_a_withdrawn_request(self):
        booking = self.request()
        self.withdraw(booking.bookingId)

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_booking(booking.bookingId, "u-venue", None)

        self.assertEqual(ctx.exception.status_code, 409)

    def test_the_withdrawal_notice_tells_venue_staff_no_action_is_needed(self):
        booking = self.withdraw(self.request().bookingId)

        subject, body = self.service.venue_staff_notice(booking, "withdrawn")

        self.assertEqual(subject, "Venue request withdrawn: AI Summit at Marina Hall A")
        self.assertTrue(body.endswith("No action is needed."))


class TestEventVenueArrangement(BookingRequestCase):
    """AC9: an event's requests can be read, so its readiness view can show a pending request as in progress."""

    def test_an_events_requests_are_listed_with_their_status(self):
        mine = self.request()
        other_venue = self.venue_named("Riverside Room")
        self.request(eventId="e-other", venueId=other_venue.venueId)

        rows = self.service.list_bookings(event_id="e-mine")

        self.assertEqual([(row.bookingId, row.status) for row in rows], [(mine.bookingId, "pending")])
        self.assertEqual(len(self.service.list_bookings(venue_id=other_venue.venueId)), 1)
