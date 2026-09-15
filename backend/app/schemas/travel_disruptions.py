"""Travel-disruption awareness API contracts."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class RoadDisruption(BaseModel):
    """One current reported road disruption."""

    disruption_id: str
    event_type: str | None = None
    event_subtype: str | None = None
    road_name: str | None = None
    description: str | None = None
    impact: str | None = None
    status: str | None = None

    latitude: float | None = None
    longitude: float | None = None

    distance_km: float | None = None

    last_updated: datetime | None = None
    end_time: datetime | None = None


class DestinationDisruptions(BaseModel):
    """Disruptions reported near one saved evacuation destination."""

    destination_id: str | None = None
    destination_name: str
    search_radius_km: float
    active_disruption_count: int
    disruptions: list[RoadDisruption] = []


class TravelDisruptionResult(BaseModel):
    """Current contextual road-disruption information for a household plan."""

    status: Literal["available", "unavailable", "not_applicable"]
    checked_at: datetime

    primary_destination: DestinationDisruptions | None = None
    backup_destinations: list[DestinationDisruptions] = []

    unavailable_reason: str | None = None

    disclaimer: str = (
        "Nearby reported road disruptions do not necessarily mean your "
        "planned travel route is blocked or unsafe."
    )