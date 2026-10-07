"""SPM-122: flag bookings that clash under the new window."""

from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.venue_activity_log import VenueActivityLog
from app.models.venue_booking import VenueBooking
from app.schemas.venue import OperatingHours, VenueUpdate
from shared.auth.deps import require_authenticated_user
from tests.unit.support import CALLER, VenueCase, booking_create, venue_create
from tests.unit.test_venue_route_guards import HEADERS, signed_in_as

MONDAY = datetime(2030, 1, 7)
ALL_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def at(hour, minute=0):
    return MONDAY + timedelta(hours=hour, minutes=minute)


def snapshot(row):
    """Every column of a booking, to show nothing about it changed."""
    return {column.key: getattr(row, column.key) for column in VenueBooking.__mapper__.column_attrs}


class ClashCase(VenueCase):
    """A hall with no setup or turnaround, so bookings that only touch are all
    approved; Venue Staff then apply the customer's 30 and 45 minutes."""

    def setUp(self):
        super().setUp()
        self.hall = self.add_venue("Harbour Hall", "HH")

    def add_venue(self, name, code):
        return self.service.create_venue(
            venue_create(
                name=name,
                code=code,
                setupMinutes=0,
                turnaroundMinutes=0,
                operatingHours=[OperatingHours(day=d, opens="00:00", closes="24:00") for d in ALL_DAYS],
            ),
            CALLER,
        )

    def booking(self, venue, event_id, starts_at, ends_at, status="approved", name=None):
        created = self.service.create_booking(
            booking_create(venue.venueId, eventId=event_id, startsAt=starts_at, endsAt=ends_at),
            "u-coord",
            event_snapshot={"eventName": name or f"Event {event_id}"},
        )
        if status == "approved":
            self.service.approve_booking(created.bookingId, "u-venue", None)
        elif status == "rejected":
            self.service.reject_booking(created.bookingId, "u-venue", "Not suitable")
        elif status == "withdrawn":
            self.service.withdraw_booking(created.bookingId, {"userId": "u-coord"}, "u-coord")
        return created.bookingId

    def apply(self, venue, setup=30, turnaround=45):
        self.service.update_venue(
            venue.venueId, VenueUpdate(setupMinutes=setup, turnaroundMinutes=turnaround), CALLER
        )

    def pairs(self, venue_id=None):
        return [(c.first.eventId, c.second.eventId) for c in self.service.booking_clashes(venue_id)]


class TestEveryOverlappingPairIsListed(ClashCase):
    """AC1: every pair of bookings on the same venue whose occupied windows overlap."""

    def setUp(self):
        super().setUp()
        # Approved while the hall needed no setup or turnaround, so touching times were fine.
        self.booking(self.hall, "ea", at(10), at(12))  # becomes 09:30 to 12:45
        self.booking(self.hall, "eb", at(12), at(13))  # becomes 11:30 to 13:45
        self.booking(self.hall, "ec", at(13), at(14))  # becomes 12:30 to 14:45
        self.booking(self.hall, "ed", at(15, 15), at(16))  # becomes 14:45 to 16:45, touching ec

    def test_nothing_clashes_before_setup_and_turnaround_are_applied(self):
        self.assertEqual(self.service.booking_clashes(), [])

    def test_every_overlapping_pair_is_listed_once_they_are_applied(self):
        self.apply(self.hall)

        # ea and ec are not neighbours, but ea's turnaround reaches into ec's setup.
        self.assertEqual(self.pairs(), [("ea", "eb"), ("ea", "ec"), ("eb", "ec")])

    def test_windows_that_only_touch_are_not_listed(self):
        self.apply(self.hall)

        self.assertNotIn(("ec", "ed"), self.pairs())

    def test_the_list_follows_the_venues_current_times(self):
        self.apply(self.hall, setup=0, turnaround=30)  # ea to 12:30, eb to 13:30, ec to 14:30
        self.assertEqual(self.pairs(), [("ea", "eb"), ("eb", "ec")])

        self.apply(self.hall, setup=0, turnaround=0)
        self.assertEqual(self.pairs(), [])

    def test_only_confirmed_bookings_are_listed(self):
        for status in ("pending", "rejected", "withdrawn"):
            self.booking(self.hall, f"e-{status}", at(11), at(12), status=status)
        self.apply(self.hall)

        listed = {event for pair in self.pairs() for event in pair}
        self.assertEqual(listed, {"ea", "eb", "ec"})

    def test_bookings_on_different_venues_never_pair_up(self):
        annex = self.add_venue("Annex Room", "AR")
        self.booking(annex, "e-annex-1", at(10), at(12))
        self.booking(annex, "e-annex-2", at(12), at(13))
        self.apply(self.hall)

        self.assertEqual(self.pairs(annex.venueId), [])
        self.apply(annex, setup=15, turnaround=0)
        # Venues in name order: Annex Room before Harbour Hall.
        self.assertEqual(self.pairs(), [("e-annex-1", "e-annex-2"), ("ea", "eb"), ("ea", "ec"), ("eb", "ec")])

    def test_one_venue_can_be_asked_for(self):
        annex = self.add_venue("Annex Room", "AR")
        self.booking(annex, "e-annex-1", at(10), at(12))
        self.booking(annex, "e-annex-2", at(12), at(13))
        self.apply(self.hall)
        self.apply(annex, setup=15, turnaround=0)

        self.assertEqual(self.pairs(annex.venueId), [("e-annex-1", "e-annex-2")])
        self.assertEqual(self.pairs(self.hall.venueId), [("ea", "eb"), ("ea", "ec"), ("eb", "ec")])

    def test_an_unknown_venue_is_not_found(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.booking_clashes("no-such-venue")

        self.assertEqual(ctx.exception.status_code, 404)


class TestWhatTheListSays(ClashCase):
    """AC2: the venue, both events, and the overlapping times."""

    def test_a_clash_names_the_venue_both_events_and_the_overlap(self):
        first = self.booking(self.hall, "ea", at(10), at(12), name="AI Summit")
        second = self.booking(self.hall, "eb", at(12), at(13), name="Board Dinner")
        self.apply(self.hall)

        (clash,) = self.service.booking_clashes()

        self.assertEqual(
            (clash.venueId, clash.venueName, clash.setupMinutes, clash.turnaroundMinutes),
            (self.hall.venueId, "Harbour Hall", 30, 45),
        )
        self.assertEqual(
            (clash.first.bookingId, clash.first.eventId, clash.first.eventName, clash.first.status),
            (first, "ea", "AI Summit", "approved"),
        )
        self.assertEqual(
            (clash.first.startsAt, clash.first.endsAt, clash.first.setupStartsAt, clash.first.teardownEndsAt),
            (at(10), at(12), at(9, 30), at(12, 45)),
        )
        self.assertEqual(
            (clash.second.bookingId, clash.second.eventId, clash.second.eventName),
            (second, "eb", "Board Dinner"),
        )
        self.assertEqual(
            (clash.second.startsAt, clash.second.endsAt, clash.second.setupStartsAt, clash.second.teardownEndsAt),
            (at(12), at(13), at(11, 30), at(13, 45)),
        )
        self.assertEqual((clash.overlapStartsAt, clash.overlapEndsAt), (at(11, 30), at(12, 45)))

    def test_a_window_inside_another_overlaps_for_its_whole_length(self):
        self.booking(self.hall, "e-long", at(9), at(17))  # becomes 08:30 to 17:45
        # An older confirmed booking inside it, saved before the clash rule existed.
        self.db.add(
            VenueBooking(
                bookingId="vb-inside",
                venueId=self.hall.venueId,
                eventId="e-inside",
                requestedBy="u-coord",
                status="approved",
                startsAt=at(10),
                endsAt=at(11),
                setupStartsAt=at(10),
                teardownEndsAt=at(11),
                createdAt=at(0),
            )
        )
        self.db.commit()
        self.apply(self.hall)  # e-inside becomes 09:30 to 11:45

        (clash,) = self.service.booking_clashes()

        self.assertEqual((clash.first.eventId, clash.second.eventId), ("e-long", "e-inside"))
        self.assertEqual((clash.overlapStartsAt, clash.overlapEndsAt), (at(9, 30), at(11, 45)))

    def test_an_older_booking_without_event_facts_is_named_by_its_event_id(self):
        self.booking(self.hall, "ea", at(10), at(12))
        self.db.add(
            VenueBooking(
                bookingId="vb-legacy",
                venueId=self.hall.venueId,
                eventId="e-legacy",
                requestedBy="u-coord",
                status="approved",
                startsAt=at(12),
                endsAt=at(13),
                setupStartsAt=at(12),
                teardownEndsAt=at(13),
                createdAt=at(0),
            )
        )
        self.db.commit()
        self.apply(self.hall)

        (clash,) = self.service.booking_clashes()

        self.assertEqual((clash.second.eventId, clash.second.eventName), ("e-legacy", None))
        # Its window comes from the hall's current times, not the stored one (SPM-112 AC1).
        self.assertEqual((clash.second.setupStartsAt, clash.second.teardownEndsAt), (at(11, 30), at(13, 45)))


class TestNothingIsChanged(ClashCase):
    """AC3 and AC4: listed bookings are kept as they were, and their events are not touched."""

    def setUp(self):
        super().setUp()
        self.booking(self.hall, "ea", at(10), at(12))
        self.booking(self.hall, "eb", at(12), at(13))
        self.apply(self.hall)

    def test_listing_leaves_every_booking_and_the_activity_log_as_they_were(self):
        before = [snapshot(row) for row in self.db.query(VenueBooking).order_by(VenueBooking.bookingId)]
        log_entries = self.db.query(VenueActivityLog).count()

        self.assertEqual(len(self.service.booking_clashes()), 1)
        self.db.expire_all()

        after = [snapshot(row) for row in self.db.query(VenueBooking).order_by(VenueBooking.bookingId)]
        self.assertEqual(after, before)
        self.assertEqual({row["status"] for row in after}, {"approved"})
        self.assertEqual(self.db.query(VenueActivityLog).count(), log_entries)

    def test_applying_setup_and_turnaround_keeps_the_bookings(self):
        rows = self.service.list_bookings("approved", None, self.hall.venueId)

        self.assertEqual(sorted(row.eventId for row in rows), ["ea", "eb"])


class TestClashRoute(ClashCase):
    def setUp(self):
        super().setUp()
        self.booking(self.hall, "ea", at(10), at(12))
        self.booking(self.hall, "eb", at(12), at(13))
        self.apply(self.hall)
        app.dependency_overrides[require_authenticated_user] = lambda: {"uid": "uid-1"}
        self.client = TestClient(app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        app.dependency_overrides.clear()
        super().tearDown()

    def clashes(self, role, **params):
        with signed_in_as(role):
            return self.client.get("/venues/bookings/clashes", headers=HEADERS, params=params)

    def test_venue_staff_get_the_list_without_any_event_being_read_or_changed(self):
        with patch("app.routers.venue.fetch_event_facts") as fetch, patch(
            "app.routers.venue.notify_venue_staff"
        ) as notify, patch("app.orchestration.clients.httpx") as outbound:
            listed = self.clashes("venue")

        self.assertEqual(listed.status_code, 200)
        self.assertEqual([(c["first"]["eventId"], c["second"]["eventId"]) for c in listed.json()], [("ea", "eb")])
        self.assertEqual(listed.json()[0]["venueName"], "Harbour Hall")
        fetch.assert_not_called()
        notify.assert_not_called()
        outbound.assert_not_called()

    def test_one_venue_or_an_unknown_venue(self):
        self.assertEqual(len(self.clashes("venue", venueId=self.hall.venueId).json()), 1)
        self.assertEqual(self.clashes("venue", venueId="no-such-venue").status_code, 404)

    def test_other_roles_cannot_see_the_list(self):
        for role in ("coordinator", "organiser", "techsupport", "attendee"):
            with self.subTest(role=role):
                self.assertEqual(self.clashes(role).status_code, 403)

    def test_signing_in_is_required(self):
        app.dependency_overrides.clear()

        self.assertEqual(self.client.get("/venues/bookings/clashes").status_code, 401)
