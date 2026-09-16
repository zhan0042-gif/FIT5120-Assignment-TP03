"""
MySQL-backed runtime spatial lookups for FIREBREAK Open Data.

This module queries the processed spatial datasets previously ingested into
MySQL. It provides Bushfire Prone Area, CFA Fire District, and Historical Fire
context without loading GeoParquet datasets into Backend memory.
"""

import math
import os
from contextlib import contextmanager

import pymysql


OPEN_DATA_DB_TIMEOUT_DEFAULTS = {
    "APP_OPEN_DATA_DB_CONNECT_TIMEOUT_SECONDS": 5,
    "APP_OPEN_DATA_DB_READ_TIMEOUT_SECONDS": 15,
    "APP_OPEN_DATA_DB_WRITE_TIMEOUT_SECONDS": 10,
}


def get_open_data_db_timeouts():
    """Return validated finite socket timeouts for direct Open Data queries."""
    values = {}
    for name, default in OPEN_DATA_DB_TIMEOUT_DEFAULTS.items():
        raw_value = os.getenv(name, str(default))
        try:
            value = int(raw_value)
        except ValueError as exc:
            raise RuntimeError(f"{name} must be a positive integer.") from exc
        if value <= 0:
            raise RuntimeError(f"{name} must be a positive integer.")
        values[name] = value
    return {
        "connect_timeout": values[
            "APP_OPEN_DATA_DB_CONNECT_TIMEOUT_SECONDS"
        ],
        "read_timeout": values["APP_OPEN_DATA_DB_READ_TIMEOUT_SECONDS"],
        "write_timeout": values[
            "APP_OPEN_DATA_DB_WRITE_TIMEOUT_SECONDS"
        ],
    }


@contextmanager
def get_connection():
    """
    Create and manage a MySQL connection for runtime spatial lookups.

    Connection settings are read from environment variables. DATABASE_HOST and
    DATABASE_PORT allow the same code to work with Docker MySQL locally and
    AWS RDS in production.

    Yields:
        pymysql.connections.Connection:
            A MySQL connection configured with dictionary-style cursors.
    """
    connection = pymysql.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
        **get_open_data_db_timeouts(),
    )

    try:
        yield connection
    finally:
        connection.close()


def check_bpa(cursor, latitude, longitude):
    """
    Determine whether a coordinate lies inside a Bushfire Prone Area.

    Args:
        cursor:
            Active PyMySQL cursor.
        latitude:
            Latitude of the location in decimal degrees, EPSG:4326.
        longitude:
            Longitude of the location in decimal degrees, EPSG:4326.

    Returns:
        bool:
            True when the location intersects a stored BPA polygon,
            otherwise False.
    """
    point_wkt = f"POINT({longitude} {latitude})"

    sql = """
        SELECT EXISTS (
            SELECT 1
            FROM open_data_bpa
            WHERE ST_Intersects(
                geometry,
                ST_GeomFromText(
                    %s,
                    4326,
                    'axis-order=long-lat'
                )
            )
        ) AS is_bushfire_prone_area
    """

    cursor.execute(sql, (point_wkt,))
    row = cursor.fetchone()

    return bool(row["is_bushfire_prone_area"])


def get_fire_district(cursor, latitude, longitude):
    """
    Return the CFA Fire District containing a coordinate.

    Args:
        cursor:
            Active PyMySQL cursor.
        latitude:
            Latitude of the location in decimal degrees, EPSG:4326.
        longitude:
            Longitude of the location in decimal degrees, EPSG:4326.

    Returns:
        str | None:
            CFA Fire District name when a matching polygon is found,
            otherwise None.
    """
    point_wkt = f"POINT({longitude} {latitude})"

    sql = """
        SELECT fire_district
        FROM open_data_fire_district
        WHERE ST_Intersects(
            geometry,
            ST_GeomFromText(
                %s,
                4326,
                'axis-order=long-lat'
            )
        )
        LIMIT 1
    """

    cursor.execute(sql, (point_wkt,))
    row = cursor.fetchone()

    if row is None:
        return None

    return row["fire_district"]


def get_fire_history_context(
    cursor,
    latitude,
    longitude,
    radius_km=20,
):
    """
    Return contextual Historical Fire information around a location.

    A geographic bounding box is first used as a spatial-index prefilter.
    ST_Distance_Sphere is then applied to the candidate points to perform the
    final radius check.

    Args:
        cursor:
            Active PyMySQL cursor.
        latitude:
            Latitude of the search location in decimal degrees, EPSG:4326.
        longitude:
            Longitude of the search location in decimal degrees, EPSG:4326.
        radius_km:
            Search radius in kilometres. Defaults to 20.

    Returns:
        dict:
            Historical Fire context containing:
            - historical_fire_record_count
            - last_recorded_burn_year
            - most_recent_fire_date
            - search_radius_km

    Notes:
        Historical Fire results are contextual information only and must not
        be interpreted as a personalised bushfire risk prediction.
    """
    latitude_delta = radius_km / 110.574

    longitude_scale = 111.320 * math.cos(
        math.radians(latitude)
    )

    if abs(longitude_scale) < 1e-9:
        longitude_delta = 180.0
    else:
        longitude_delta = radius_km / abs(longitude_scale)

    min_lon = longitude - longitude_delta
    max_lon = longitude + longitude_delta
    min_lat = latitude - latitude_delta
    max_lat = latitude + latitude_delta

    point_wkt = f"POINT({longitude} {latitude})"

    bbox_wkt = (
        "POLYGON(("
        f"{min_lon} {min_lat},"
        f"{max_lon} {min_lat},"
        f"{max_lon} {max_lat},"
        f"{min_lon} {max_lat},"
        f"{min_lon} {min_lat}"
        "))"
    )

    sql = """
        SELECT
            COUNT(*) AS historical_fire_record_count,
            MAX(season) AS last_recorded_burn_year,
            MAX(start_date) AS most_recent_fire_date
        FROM open_data_fire_history
        WHERE MBRContains(
            ST_GeomFromText(
                %s,
                4326,
                'axis-order=long-lat'
            ),
            geometry
        )
        AND ST_Distance_Sphere(
            geometry,
            ST_GeomFromText(
                %s,
                4326,
                'axis-order=long-lat'
            )
        ) <= %s
    """

    cursor.execute(
        sql,
        (
            bbox_wkt,
            point_wkt,
            radius_km * 1000,
        ),
    )

    row = cursor.fetchone()

    most_recent_fire_date = row["most_recent_fire_date"]

    if most_recent_fire_date is not None:
        most_recent_fire_date = most_recent_fire_date.isoformat()

    return {
        "historical_fire_record_count": int(
            row["historical_fire_record_count"]
        ),
        "last_recorded_burn_year": (
            int(row["last_recorded_burn_year"])
            if row["last_recorded_burn_year"] is not None
            else None
        ),
        "most_recent_fire_date": most_recent_fire_date,
        "search_radius_km": radius_km,
    }


def get_fire_history_points(
    cursor,
    latitude,
    longitude,
    radius_km=20,
    limit=500,
):
    """
    Return Historical Fire point records within a radius of a location.

    The query first applies a rectangular bounding-box filter so MySQL can
    use the spatial index. It then applies ST_Distance_Sphere to keep only
    records that fall within the requested radius.

    Args:
        cursor:
            Active PyMySQL dictionary cursor.
        latitude:
            Latitude of the household location in decimal degrees,
            EPSG:4326.
        longitude:
            Longitude of the household location in decimal degrees,
            EPSG:4326.
        radius_km:
            Search radius around the household in kilometres.
            Defaults to 20.
        limit:
            Maximum number of points returned. Applied by MySQL.

    Returns:
        list[dict]:
            Historical Fire records within the requested radius. Each
            dictionary contains latitude, longitude, season, and start_date.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError(
            "Historical Fire point limit must be a positive integer."
        )

    latitude_delta = radius_km / 110.574

    longitude_scale = 111.320 * math.cos(
        math.radians(latitude)
    )

    if abs(longitude_scale) < 1e-9:
        longitude_delta = 180.0
    else:
        longitude_delta = radius_km / abs(longitude_scale)

    min_lon = longitude - longitude_delta
    max_lon = longitude + longitude_delta
    min_lat = latitude - latitude_delta
    max_lat = latitude + latitude_delta

    point_wkt = f"POINT({longitude} {latitude})"

    bbox_wkt = (
        "POLYGON(("
        f"{min_lon} {min_lat},"
        f"{max_lon} {min_lat},"
        f"{max_lon} {max_lat},"
        f"{min_lon} {max_lat},"
        f"{min_lon} {min_lat}"
        "))"
    )

    sql = """
        WITH candidates AS (
            SELECT
                fire_history_id,
                ST_Longitude(geometry) AS longitude,
                ST_Latitude(geometry) AS latitude,
                season,
                start_date,
                ST_Distance_Sphere(
                    geometry,
                    ST_GeomFromText(
                        %s,
                        4326,
                        'axis-order=long-lat'
                    )
                ) AS distance_meters
            FROM open_data_fire_history
            WHERE MBRContains(
                ST_GeomFromText(
                    %s,
                    4326,
                    'axis-order=long-lat'
                ),
                geometry
            )
        )
        SELECT latitude, longitude, season, start_date, distance_meters
        FROM candidates
        WHERE distance_meters <= %s
        ORDER BY
            start_date IS NULL,
            start_date DESC,
            season IS NULL,
            season DESC,
            fire_history_id DESC
        LIMIT %s
    """

    cursor.execute(
        sql,
        (
            point_wkt,
            bbox_wkt,
            radius_km * 1000,
            limit,
        ),
    )

    rows = cursor.fetchall()

    return [
        {
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "season": (
                int(row["season"])
                if row["season"] is not None
                else None
            ),
            "start_date": (
                row["start_date"].isoformat()
                if row["start_date"] is not None
                else None
            ),
            "distance_km": float(row["distance_meters"]) / 1000,
        }
        for row in rows
    ]


def get_nearest_fire_history_point(
    cursor,
    latitude,
    longitude,
    radius_km=20,
):
    """Return the nearest representative fire point inside the search radius."""
    latitude_delta = radius_km / 110.574
    longitude_scale = 111.320 * math.cos(math.radians(latitude))
    longitude_delta = (
        180.0
        if abs(longitude_scale) < 1e-9
        else radius_km / abs(longitude_scale)
    )

    min_lon = longitude - longitude_delta
    max_lon = longitude + longitude_delta
    min_lat = latitude - latitude_delta
    max_lat = latitude + latitude_delta
    point_wkt = f"POINT({longitude} {latitude})"
    bbox_wkt = (
        "POLYGON(("
        f"{min_lon} {min_lat},"
        f"{max_lon} {min_lat},"
        f"{max_lon} {max_lat},"
        f"{min_lon} {max_lat},"
        f"{min_lon} {min_lat}"
        "))"
    )

    sql = """
        WITH candidates AS (
            SELECT
                fire_history_id,
                ST_Longitude(geometry) AS longitude,
                ST_Latitude(geometry) AS latitude,
                season,
                start_date,
                ST_Distance_Sphere(
                    geometry,
                    ST_GeomFromText(
                        %s,
                        4326,
                        'axis-order=long-lat'
                    )
                ) AS distance_meters
            FROM open_data_fire_history
            WHERE MBRContains(
                ST_GeomFromText(
                    %s,
                    4326,
                    'axis-order=long-lat'
                ),
                geometry
            )
        )
        SELECT latitude, longitude, season, start_date, distance_meters
        FROM candidates
        WHERE distance_meters <= %s
        ORDER BY distance_meters ASC, fire_history_id DESC
        LIMIT 1
    """

    cursor.execute(sql, (point_wkt, bbox_wkt, radius_km * 1000))
    row = cursor.fetchone()
    if row is None:
        return None
    return {
        "latitude": float(row["latitude"]),
        "longitude": float(row["longitude"]),
        "season": int(row["season"]) if row["season"] is not None else None,
        "start_date": (
            row["start_date"].isoformat()
            if row["start_date"] is not None
            else None
        ),
        "distance_km": float(row["distance_meters"]) / 1000,
    }
