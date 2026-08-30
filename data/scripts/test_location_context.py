import json

from location_context import get_location_context


test_latitude = -37.89002627699995
test_longitude = 144.12595975369607

result = get_location_context(
    test_latitude,
    test_longitude
)

print(
    json.dumps(
        result,
        indent=2
    )
)


# Basic structure validation

required_top_level_keys = {
    "location",
    "is_bushfire_prone_area",
    "fire_district",
    "environmental_context"
}

top_level_ok = required_top_level_keys.issubset(
    result.keys()
)

fire_history = result[
    "environmental_context"
]["fire_history"]

required_fire_history_keys = {
    "historical_fire_record_count",
    "last_recorded_burn_year",
    "most_recent_fire_date",
    "search_radius_km"
}

fire_history_ok = required_fire_history_keys.issubset(
    fire_history.keys()
)

print("\nValidation:")
print("Top-level structure valid:", top_level_ok)
print("Fire History structure valid:", fire_history_ok)