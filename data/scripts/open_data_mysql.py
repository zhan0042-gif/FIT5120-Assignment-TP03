import math
import os
from contextlib import contextmanager

import pymysql
from dotenv import load_dotenv


load_dotenv()


@contextmanager
def get_connection():
    connection = pymysql.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "3306")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

    try:
        yield connection
    finally:
        connection.close()


def check_bpa(cursor, latitude, longitude):
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