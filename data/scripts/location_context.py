from .open_data_mysql import (
    check_bpa,
    get_connection,
    get_fire_district,
    get_fire_history_context,
    get_fire_history_points,
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
    Return the combined FIREBREAK spatial context for a location.

    The function queries MySQL for:
    - Bushfire Prone Area membership
    - CFA Fire District
    - Historical Fire context within the configured radius

    Args:
        latitude:
            Latitude of the location in decimal degrees, EPSG:4326.
        longitude:
            Longitude of the location in decimal degrees, EPSG:4326.
        fire_history_radius_km:
            Radius in kilometres used for the Historical Fire lookup.
            Defaults to 20.

    Returns:
        dict:
            Application-ready spatial context containing location coordinates,
            BPA status, CFA Fire District, and Historical Fire context.

    Notes:
        Historical Fire information is contextual only and must not be
        interpreted as a personalised bushfire risk score or prediction.
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

            fire_history_points = get_fire_history_points(
                cursor,
                latitude,
                longitude,
                radius_km=fire_history_radius_km,
            )

    fire_history["historical_fire_points"] = fire_history_points

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