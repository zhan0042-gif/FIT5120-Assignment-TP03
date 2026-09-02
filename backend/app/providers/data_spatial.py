"""Adapter from the Iteration 1 Data lookup to the Backend provider contract."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import ExternalDataUnavailable


LocationLookup = Callable[[float, float], dict[str, Any]]


@dataclass(frozen=True)
class DataSpatialResult:
    is_bushfire_prone_area: bool
    fire_district: str
    fire_history_summary: str | None
    vegetation_context: str | None = None
    terrain_context: str | None = None
    fire_history_record_count: int | None = None
    fire_history_latest_year: int | None = None
    fire_history_latest_date: str | None = None
    fire_history_radius_km: float | None = None


class DataSpatialProvider:
    """Expose Data's combined location lookup through ``SpatialProvider``."""

    def __init__(self, lookup: LocationLookup | None = None) -> None:
        self._lookup = lookup

    def get_context(self, latitude: float, longitude: float) -> DataSpatialResult:
        try:
            context = self._location_lookup()(latitude, longitude)
            district = context.get("fire_district")
            if not isinstance(district, str) or not district.strip():
                raise ExternalDataUnavailable(
                    "No Victorian CFA fire district was found for this location."
                )
            environmental = context.get("environmental_context") or {}
            history = environmental.get("fire_history")
            return DataSpatialResult(
                is_bushfire_prone_area=bool(
                    context.get("is_bushfire_prone_area", False)
                ),
                fire_district=district,
                fire_history_summary=self._fire_history_summary(history),
                fire_history_record_count=(
                    history.get("historical_fire_record_count")
                    if isinstance(history, dict) else None
                ),
                fire_history_latest_year=(
                    history.get("last_recorded_burn_year")
                    if isinstance(history, dict) else None
                ),
                fire_history_latest_date=(
                    history.get("most_recent_fire_date")
                    if isinstance(history, dict) else None
                ),
                fire_history_radius_km=(
                    history.get("search_radius_km")
                    if isinstance(history, dict) else None
                ),
            )
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Spatial context data is unavailable."
            ) from exc

    def _location_lookup(self) -> LocationLookup:
        if self._lookup is None:
            from data.scripts.location_context import get_location_context

            self._lookup = get_location_context
        return self._lookup

    @staticmethod
    def _fire_history_summary(history: Any) -> str | None:
        if not isinstance(history, dict):
            return None
        count = history.get("historical_fire_record_count")
        radius = history.get("search_radius_km")
        if not isinstance(count, int) or not isinstance(radius, (int, float)):
            return None
        radius_text = f"{radius:g}"
        if count == 0:
            return f"No historical bushfire records were found within {radius_text} km."
        summary = (
            f"{count} historical bushfire record"
            f"{'s' if count != 1 else ''} were found within {radius_text} km."
        )
        burn_year = history.get("last_recorded_burn_year")
        recent_date = history.get("most_recent_fire_date")
        if isinstance(burn_year, int):
            summary += f" The latest recorded burn season was {burn_year}."
        if isinstance(recent_date, str) and recent_date:
            summary += f" The most recent dated record was {recent_date}."
        return summary
