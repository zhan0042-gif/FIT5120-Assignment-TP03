import geopandas as gpd
from shapely.geometry import Point

from fire_history_lookup import get_fire_history_context


# --------------------------------------------------
# Load processed application-ready datasets
# --------------------------------------------------

BPA_PATH = "data/processed/bpa.parquet"
FIRE_DISTRICT_PATH = "data/processed/fire_district.parquet"

bpa = gpd.read_parquet(BPA_PATH)
fire_district = gpd.read_parquet(FIRE_DISTRICT_PATH)


# --------------------------------------------------
# BPA lookup
# --------------------------------------------------

def check_bpa(latitude, longitude):
    point = Point(longitude, latitude)

    match = bpa[
        bpa.geometry.covers(point)
    ]

    return not match.empty


# --------------------------------------------------
# CFA Fire District lookup
# --------------------------------------------------

def get_fire_district(latitude, longitude):
    point = Point(longitude, latitude)

    match = fire_district[
        fire_district.geometry.covers(point)
    ]

    if match.empty:
        return None

    return match.iloc[0]["fire_district"]


# --------------------------------------------------
# Combined location context
# --------------------------------------------------

def get_location_context(
    latitude,
    longitude,
    fire_history_radius_km=20
):
    """
    Return application-ready location context.

    This combines:
    - Bushfire Prone Area status
    - CFA Fire District
    - Historical bushfire context

    Fire History is contextual only and must not be
    interpreted as a personalised bushfire risk score.
    """

    return {
        "location": {
            "latitude": float(latitude),
            "longitude": float(longitude)
        },
        "is_bushfire_prone_area": bool(
            check_bpa(latitude, longitude)
        ),
        "fire_district": get_fire_district(
            latitude,
            longitude
        ),
        "environmental_context": {
            "fire_history": get_fire_history_context(
                latitude,
                longitude,
                radius_km=fire_history_radius_km
            )
        }
    }