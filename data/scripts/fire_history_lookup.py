import json

import geopandas as gpd
from shapely.geometry import Point


# --------------------------------------------------
# Load lightweight Fire History dataset
# --------------------------------------------------

FIRE_HISTORY_PATH = (
    "data/processed/fire_history_lightweight.parquet"
)

fire_history = gpd.read_parquet(FIRE_HISTORY_PATH)

print("Loaded Fire History records:", len(fire_history))
print("Source CRS:", fire_history.crs)


# --------------------------------------------------
# Project dataset once for distance-based lookup
# --------------------------------------------------

fire_history_projected = fire_history.to_crs(
    "EPSG:7899"
)

print("Lookup CRS:", fire_history_projected.crs)


# --------------------------------------------------
# Fire History lookup
# --------------------------------------------------

def get_fire_history_context(
    latitude,
    longitude,
    radius_km=20
):
    """
    Return historical bushfire context around a location.

    The lightweight dataset contains one representative
    point for each historical bushfire polygon.

    The result is contextual information only.
    It does not calculate or predict bushfire risk.
    """

    location = gpd.GeoSeries(
        [Point(longitude, latitude)],
        crs="EPSG:4326"
    )

    location_projected = location.to_crs(
        "EPSG:7899"
    )

    search_area = location_projected.buffer(
        radius_km * 1000
    ).iloc[0]

    matching_indices = (
        fire_history_projected.sindex.query(
            search_area,
            predicate="intersects"
        )
    )

    nearby_fires = fire_history_projected.iloc[
        matching_indices
    ].copy()

    if nearby_fires.empty:
        return {
            "historical_fire_record_count": 0,
            "last_recorded_burn_year": None,
            "most_recent_fire_date": None,
            "search_radius_km": radius_km
        }

    valid_dates = nearby_fires[
        "start_date"
    ].dropna()

    if valid_dates.empty:
        most_recent_fire_date = None
    else:
        most_recent_fire_date = (
            valid_dates.max()
            .date()
            .isoformat()
        )

    return {
        "historical_fire_record_count": int(
            len(nearby_fires)
        ),
        "last_recorded_burn_year": int(
            nearby_fires["season"].max()
        ),
        "most_recent_fire_date": most_recent_fire_date,
        "search_radius_km": radius_km
    }


# --------------------------------------------------
# Example lookup
# --------------------------------------------------

test_latitude = -37.89002627699995
test_longitude = 144.12595975369607

result = get_fire_history_context(
    test_latitude,
    test_longitude,
    radius_km=20
)

print("\nExample Fire History context:")
print(
    json.dumps(
        result,
        indent=2
    )
)


# --------------------------------------------------
# Basic validation
# --------------------------------------------------

print("\nBasic validation:")

required_keys = {
    "historical_fire_record_count",
    "last_recorded_burn_year",
    "most_recent_fire_date",
    "search_radius_km"
}

keys_ok = required_keys.issubset(
    result.keys()
)

count_ok = (
    isinstance(
        result["historical_fire_record_count"],
        int
    )
    and result["historical_fire_record_count"] >= 0
)

radius_ok = (
    result["search_radius_km"] == 20
)

print("Required keys present:", keys_ok)
print("Record count valid:", count_ok)
print("Search radius correct:", radius_ok)