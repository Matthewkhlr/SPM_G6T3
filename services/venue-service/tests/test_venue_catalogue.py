import pytest
from fastapi import HTTPException

from app.schemas.venue import VenueCreate, VenueUpdate

CALLER = {"userId": "u-venue-1", "userName": "Vera Venue", "role": "venue"}


def make_venue(**overrides):
    defaults = dict(
        code="MH-A",
        name="Marina Hall A",
        location="HarbourFront Centre",
        address="1 HarbourFront Walk, Singapore 098585",
        floor="2",
        description="Largest multipurpose hall.",
        facilities=["Projector", "PA system"],
        accessibility=["Wheelchair accessible"],
        layouts=[{"name": "Theatre", "capacity": 300}, {"name": "Classroom", "capacity": 180}],
        operatingHours=[{"day": "Mon", "opens": "08:00", "closes": "22:00"}],
        turnaroundMinutes=60,
    )
    defaults.update(overrides)
    return VenueCreate(**defaults)


def test_create_venue_derives_capacity_from_highest_layout(venue_service):
    created = venue_service.create_venue(make_venue(), CALLER)

    assert created.capacity == 300
    assert created.isActive is True
    assert len(created.layouts) == 2


def test_get_venue_returns_the_venue_just_created(venue_service):
    created = venue_service.create_venue(make_venue(code="MH-B", name="Marina Hall B"), CALLER)

    fetched = venue_service.get_venue(created.venueId)

    assert fetched.venueId == created.venueId
    assert fetched.name == "Marina Hall B"


def test_get_venue_missing_id_raises_404(venue_service):
    with pytest.raises(HTTPException) as exc_info:
        venue_service.get_venue("does-not-exist")

    assert exc_info.value.status_code == 404


def test_list_venues_excludes_retired_by_default_but_can_include_them(venue_service):
    active = venue_service.create_venue(make_venue(code="MH-C", name="Active Hall"), CALLER)
    retired = venue_service.create_venue(make_venue(code="MH-D", name="Retired Hall"), CALLER)
    venue_service.retire_venue(retired.venueId, CALLER)

    default_list = venue_service.list_venues()
    full_list = venue_service.list_venues(include_retired=True)

    assert [v.venueId for v in default_list] == [active.venueId]
    assert {v.venueId for v in full_list} == {active.venueId, retired.venueId}


def test_update_venue_partial_update_leaves_other_fields_untouched(venue_service):
    created = venue_service.create_venue(make_venue(code="MH-E", name="Hall E"), CALLER)

    updated = venue_service.update_venue(created.venueId, VenueUpdate(turnaroundMinutes=90), CALLER)

    assert updated.turnaroundMinutes == 90
    assert updated.name == "Hall E"
    assert updated.location == created.location
    assert updated.layouts == created.layouts


def test_update_venue_records_a_layout_capacity_change_in_the_activity_log(venue_service):
    created = venue_service.create_venue(make_venue(code="MH-F", name="Hall F"), CALLER)

    venue_service.update_venue(
        created.venueId,
        VenueUpdate(layouts=[{"name": "Theatre", "capacity": 350}, {"name": "Classroom", "capacity": 180}]),
        CALLER,
    )

    log = venue_service.get_activity_log(created.venueId)
    latest = log[0]
    assert latest.action == "updated"
    assert latest.changes["layouts"]["Theatre"]["capacity"] == {"old": 300, "new": 350}


def test_update_venue_with_no_actual_changes_does_not_add_an_activity_log_entry(venue_service):
    created = venue_service.create_venue(make_venue(code="MH-G", name="Hall G"), CALLER)

    venue_service.update_venue(created.venueId, VenueUpdate(name="Hall G"), CALLER)

    log = venue_service.get_activity_log(created.venueId)
    assert len(log) == 1  # only the original "created" entry
    assert log[0].action == "created"
