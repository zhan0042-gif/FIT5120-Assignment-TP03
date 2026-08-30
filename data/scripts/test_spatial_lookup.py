import geopandas as gpd
from shapely.geometry import Point
import pandas as pd
from fire_history_lookup import get_fire_history_context


# Load processed datasets
bpa = gpd.read_parquet(
    "data/processed/bpa.parquet"
)

fire_district = gpd.read_parquet(
    "data/processed/fire_district.parquet"
)


def check_bpa(latitude, longitude, bpa_gdf):
    point = Point(longitude, latitude)

    match = bpa_gdf[
        bpa_gdf.geometry.covers(point)
    ]

    return not match.empty


def get_fire_district(latitude, longitude, district_gdf):
    point = Point(longitude, latitude)

    match = district_gdf[
        district_gdf.geometry.covers(point)
    ]

    if match.empty:
        return None

    return match.iloc[0]["fire_district"]


def get_location_context(
    latitude,
    longitude,
    fire_history_radius_km=20
):
    return {
        "location": {
            "latitude": latitude,
            "longitude": longitude
        },
        "is_bushfire_prone_area": check_bpa(
            latitude,
            longitude,
            bpa
        ),
        "fire_district": get_fire_district(
            latitude,
            longitude,
            fire_district
        ),
        "environmental_context": {
            "fire_history": get_fire_history_context(
                latitude,
                longitude,
                radius_km=fire_history_radius_km
            )
        }
    }



# Example test
test_latitude = -37.89002627699995
test_longitude = 144.12595975369607

result = get_location_context(
    test_latitude,
    test_longitude
)

print(result)


print("\nSample district test points:")

for index, row in fire_district.iterrows():
    point = row.geometry.representative_point()

    latitude = point.y
    longitude = point.x

    context = get_location_context(
        latitude,
        longitude
    )

    print(
        row["fire_district"],
        "|",
        latitude,
        "|",
        longitude,
        "| BPA:",
        context["is_bushfire_prone_area"]
    )



# Combine all BPA polygons into one geometry
bpa_union = bpa.geometry.union_all()

print("\nSample non-BPA points by district:")

for _, row in fire_district.iterrows():
    district_name = row["fire_district"]

    # Remove BPA-covered area from the fire district
    non_bpa_area = row.geometry.difference(bpa_union)

    if non_bpa_area.is_empty:
        print(district_name, "| No non-BPA area found")
        continue

    # Get a point guaranteed to fall inside the remaining non-BPA area
    point = non_bpa_area.representative_point()

    latitude = point.y
    longitude = point.x

    context = get_location_context(
        latitude,
        longitude
    )

    print(
        district_name,
        "|",
        latitude,
        "|",
        longitude,
        "| BPA:",
        context["is_bushfire_prone_area"]
    )




test_cases = pd.read_csv(
    "data/test/location_test_cases.csv"
)

print("\nRunning test fixtures:")

for _, row in test_cases.iterrows():
    context = get_location_context(
        row["latitude"],
        row["longitude"]
    )

    actual_bpa = context["is_bushfire_prone_area"]
    actual_district = context["fire_district"]

    fire_history = context[
        "environmental_context"
    ]["fire_history"]

    fire_history_keys_ok = {
        "historical_fire_record_count",
        "last_recorded_burn_year",
        "most_recent_fire_date",
        "search_radius_km"
    }.issubset(
        fire_history.keys()
    )

    fire_history_count_ok = (
        isinstance(
            fire_history["historical_fire_record_count"],
            int
        )
        and fire_history["historical_fire_record_count"] >= 0
    )

    fire_history_radius_ok = (
        fire_history["search_radius_km"] == 20
    )

    bpa_ok = actual_bpa == row["expected_bpa"]
    district_ok = actual_district == row["expected_fire_district"]

    print(
        row["test_id"],
        "| BPA:",
        actual_bpa,
        "| District:",
        actual_district,
        "| BPA match:",
        bpa_ok,
        "| District match:",
        district_ok,
        "| Fire History keys:",
        fire_history_keys_ok,
        "| Fire History count:",
        fire_history_count_ok,
        "| Radius:",
        fire_history_radius_ok
    )