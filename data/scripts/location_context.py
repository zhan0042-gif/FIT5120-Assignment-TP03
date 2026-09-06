from .open_data_mysql import (
    check_bpa,
    get_connection,
    get_fire_district,
    get_fire_history_context,
)


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

    latitude = float(latitude)
    longitude = float(longitude)

    with get_connection() as connection:
        with connection.cursor() as cursor:
            is_bpa = check_bpa(
                cursor,
                latitude,
                longitude,
            )

            fire_district = get_fire_district(
                cursor,
                latitude,
                longitude,
            )

            fire_history = get_fire_history_context(
                cursor,
                latitude,
                longitude,
                radius_km=fire_history_radius_km,
            )

    return {
        "location": {
            "latitude": latitude,
            "longitude": longitude,
        },
        "is_bushfire_prone_area": bool(is_bpa),
        "fire_district": fire_district,
        "environmental_context": {
            "fire_history": fire_history,
        },
    }