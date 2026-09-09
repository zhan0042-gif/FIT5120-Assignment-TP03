"""Adapter from the Iteration 1 Data lookup to the Backend provider contract."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.exceptions import ExternalDataUnavailable


LocationLookup = Callable[[float, float], dict[str, Any]]
DistrictLookup = Callable[[float, float], str | None]


@dataclass(frozen=True)
class DataSpatialResult:
    is_bushfire_prone_area: bool
    fire_district: str
    vegetation_context: str | None = None
    terrain_context: str | None = None
    fire_history_record_count: int | None = None
    fire_history_latest_year: int | None = None
    fire_history_latest_date: str | None = None
    fire_history_radius_km: float | None = None


class DataSpatialProvider:
    """Expose MySQL-backed Open Data lookups through ``SpatialProvider``.

    The combined lookup resolves BPA, CFA district, and historical context.
    A narrow district lookup supports consumers that only need FDR matching.
    """

    def __init__(
        self,
        lookup: LocationLookup | None = None,
        district_lookup: DistrictLookup | None = None,
    ) -> None:
        self._lookup = lookup
        self._district_lookup = district_lookup

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

    def get_fire_district(self, latitude: float, longitude: float) -> str:
        try:
            district = self._fire_district_lookup()(latitude, longitude)
            if not isinstance(district, str) or not district.strip():
                raise ExternalDataUnavailable(
                    "No Victorian CFA fire district was found for this location."
                )
            return district
        except ExternalDataUnavailable:
            raise
        except Exception as exc:
            raise ExternalDataUnavailable(
                "Fire district data is unavailable."
            ) from exc

    def _location_lookup(self) -> LocationLookup:
        if self._lookup is None:
            from data.scripts.location_context import get_location_context

            self._lookup = get_location_context
        return self._lookup

    def _fire_district_lookup(self) -> DistrictLookup:
        if self._district_lookup is None:
            from data.scripts.location_context import get_location_fire_district

            self._district_lookup = get_location_fire_district
        return self._district_lookup
