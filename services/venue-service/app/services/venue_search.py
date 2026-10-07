"""SPM-61: which venues fit an event's requirements, for a shortlist.

The venue-only rules (location, layout and capacity, facilities,
accessibility, opening hours) live here. Availability is the shared SPM-64
rule, `VenueService.commitments`, which `VenueService.search_venues` applies.

All times are UTC, and a venue's opening hours are read as UTC hours.
"""

from dataclasses import dataclass, field
from datetime import datetime

from app.schemas.venue import VenueOut
from app.services.suitability import _missing, _opening_hours


@dataclass
class SearchFilters:
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    min_capacity: int = 0
    location: str | None = None
    layout: str | None = None
    facilities: list[str] = field(default_factory=list)
    accessibility: list[str] = field(default_factory=list)

    @property
    def has_period(self) -> bool:
        return self.starts_at is not None and self.ends_at is not None


def layout_capacity(venue: VenueOut, layout: str | None) -> int | None:
    """AC5: capacity in the layout searched for, the venue's overall capacity
    when none was given, or None when the venue does not offer that layout."""
    if not layout or not layout.strip():
        return venue.capacity
    wanted = layout.strip().casefold()
    match = next((item for item in venue.layouts if item.name.casefold() == wanted), None)
    return match.capacity if match else None


def fits(venue: VenueOut, filters: SearchFilters) -> int | None:
    """Every rule that needs only the venue record. Returns the capacity in the
    layout searched for when the venue fits, or None when it is excluded."""
    if filters.location and filters.location.strip().casefold() not in venue.location.casefold():
        return None
    capacity = layout_capacity(venue, filters.layout)
    if capacity is None or capacity < filters.min_capacity:
        return None
    if _missing(filters.facilities, venue.facilities) or _missing(filters.accessibility, venue.accessibility):
        return None
    if filters.has_period and _opening_hours(venue, filters.starts_at, filters.ends_at):
        return None
    return capacity
