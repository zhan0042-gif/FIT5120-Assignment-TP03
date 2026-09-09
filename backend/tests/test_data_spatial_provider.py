from importlib.util import find_spec

import pytest

from app.core.exceptions import ExternalDataUnavailable
from app.providers.data_spatial import DataSpatialProvider


def test_data_package_is_installed_for_bare_backend_runtime() -> None:
    assert find_spec("data.scripts.location_context") is not None


def test_data_spatial_provider_maps_the_data_contract() -> None:
    def lookup(latitude: float, longitude: float) -> dict:
        assert (latitude, longitude) == (-37.89, 144.12)
        return {
            "is_bushfire_prone_area": True,
            "fire_district": "Central",
            "environmental_context": {
                "fire_history": {
                    "historical_fire_record_count": 3,
                    "last_recorded_burn_year": 2024,
                    "most_recent_fire_date": "2024-02-03",
                    "search_radius_km": 20,
                }
            },
        }

    result = DataSpatialProvider(lookup).get_context(-37.89, 144.12)

    assert result.is_bushfire_prone_area is True
    assert result.fire_district == "Central"
    assert result.fire_history_record_count == 3
    assert result.fire_history_latest_year == 2024
    assert result.fire_history_latest_date == "2024-02-03"
    assert result.fire_history_radius_km == 20
    assert result.vegetation_context is None
    assert result.terrain_context is None


def test_data_spatial_provider_maps_an_empty_fire_history() -> None:
    provider = DataSpatialProvider(
        lambda _latitude, _longitude: {
            "is_bushfire_prone_area": False,
            "fire_district": "Mallee",
            "environmental_context": {
                "fire_history": {
                    "historical_fire_record_count": 0,
                    "last_recorded_burn_year": None,
                    "most_recent_fire_date": None,
                    "search_radius_km": 12.5,
                }
            },
        }
    )

    result = provider.get_context(-35.0, 142.0)

    assert result.fire_history_record_count == 0
    assert result.fire_history_latest_year is None
    assert result.fire_history_latest_date is None
    assert result.fire_history_radius_km == 12.5


def test_data_spatial_provider_supports_a_narrow_district_lookup() -> None:
    full_calls = 0
    district_calls = 0

    def full_lookup(_latitude: float, _longitude: float) -> dict:
        nonlocal full_calls
        full_calls += 1
        raise AssertionError("full context lookup should not run")

    def district_lookup(latitude: float, longitude: float) -> str:
        nonlocal district_calls
        district_calls += 1
        assert (latitude, longitude) == (-37.89, 144.12)
        return "Central"

    provider = DataSpatialProvider(full_lookup, district_lookup)

    assert provider.get_fire_district(-37.89, 144.12) == "Central"
    assert full_calls == 0
    assert district_calls == 1


def test_data_spatial_provider_rejects_narrow_lookup_without_a_district() -> None:
    provider = DataSpatialProvider(
        lambda _latitude, _longitude: {},
        lambda _latitude, _longitude: None,
    )

    with pytest.raises(ExternalDataUnavailable, match="CFA fire district"):
        provider.get_fire_district(-10.0, 120.0)


def test_data_spatial_provider_rejects_locations_without_a_district() -> None:
    provider = DataSpatialProvider(
        lambda _latitude, _longitude: {
            "is_bushfire_prone_area": False,
            "fire_district": None,
            "environmental_context": {},
        }
    )

    with pytest.raises(ExternalDataUnavailable, match="CFA fire district"):
        provider.get_context(-10.0, 120.0)


def test_data_spatial_provider_hides_lookup_failures() -> None:
    def unavailable(_latitude: float, _longitude: float) -> dict:
        raise OSError("private data path")

    with pytest.raises(
        ExternalDataUnavailable, match="Spatial context data is unavailable"
    ):
        DataSpatialProvider(unavailable).get_context(-37.89, 144.12)
