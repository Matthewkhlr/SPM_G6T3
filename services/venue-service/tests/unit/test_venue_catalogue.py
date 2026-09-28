from fastapi import HTTPException

from app.schemas.venue import Layout, OperatingHours, VenueUpdate
from tests.unit.support import CALLER, VenueCase, venue_create


class TestVenueCatalogue(VenueCase):
    def test_session_dependency_closes_and_init_db_is_a_noop(self):
        self.close_db_dependency()

    def test_create_venue_derives_capacity_from_the_largest_layout(self):
        created = self.service.create_venue(venue_create(), CALLER)

        self.assertEqual(created.capacity, 100)
        self.assertEqual(created.name, "Marina Hall A")
        self.assertTrue(created.isActive)
        self.assertEqual(len(self.service.get_activity_log(created.venueId)), 1)

    def test_missing_venue_and_booking_are_404(self):
        with self.assertRaises(HTTPException) as ctx:
            self.service.get_venue("missing")
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx:
            self.service.get_activity_log("missing")
        self.assertEqual(ctx.exception.status_code, 404)

        with self.assertRaises(HTTPException) as ctx:
            self.service.approve_booking("missing", "u-venue", None)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_list_hides_retired_venues_unless_asked(self):
        created = self.service.create_venue(venue_create(), CALLER)
        self.service.retire_venue(created.venueId, CALLER)

        self.assertEqual(self.service.list_venues(), [])
        self.assertEqual(self.service.list_venues(include_retired=True)[0].venueId, created.venueId)
        self.assertFalse(self.service.get_venue(created.venueId).isActive)

    def test_update_venue_logs_each_kind_of_change(self):
        created = self.service.create_venue(venue_create(), CALLER)

        updated = self.service.update_venue(
            created.venueId,
            VenueUpdate(
                name="Marina Hall B",
                facilities=["PA", "Stage"],
                accessibility=["Lift"],
                layouts=[Layout(name="Theatre", capacity=80)],
                operatingHours=[OperatingHours(day="Tue", opens="09:00", closes="17:00")],
                turnaroundMinutes=30,
            ),
            CALLER,
        )

        self.assertEqual(updated.name, "Marina Hall B")
        self.assertEqual(updated.capacity, 80)
        actions = [row.action for row in self.service.get_activity_log(created.venueId)]
        self.assertIn("updated", actions)

    def test_update_with_the_same_values_does_not_add_an_update_log(self):
        created = self.service.create_venue(venue_create(), CALLER)

        self.service.update_venue(created.venueId, VenueUpdate(name="Marina Hall A"), CALLER)

        actions = [row.action for row in self.service.get_activity_log(created.venueId)]
        self.assertEqual(actions, ["created"])

    def test_update_accepts_layout_and_hours_model_instances(self):
        created = self.service.create_venue(venue_create(layouts=[], operatingHours=[]), {"userId": "u-venue"})

        class Payload:
            def model_dump(self, exclude_unset=True):
                return {
                    "layouts": [Layout(name="Theatre", capacity=12)],
                    "operatingHours": [OperatingHours(day="Mon", opens="09:00", closes="17:00")],
                }

        updated = self.service.update_venue(created.venueId, Payload(), CALLER)

        self.assertEqual(updated.capacity, 12)
        self.assertEqual(updated.operatingHours[0].day, "Mon")
