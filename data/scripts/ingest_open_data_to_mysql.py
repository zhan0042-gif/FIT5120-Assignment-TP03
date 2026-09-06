"""
Load processed FIREBREAK spatial Open Data into MySQL.

This script ingests:
- Bushfire Prone Area polygons
- CFA Fire District polygons
- lightweight Historical Fire representative points

The processed GeoParquet files remain the reproducible application-ready
data artifacts, while MySQL becomes the runtime storage used by Backend.
"""

import os

import geopandas as gpd
import pandas as pd
import pymysql


BPA_PATH = "data/processed/bpa.parquet"
FIRE_DISTRICT_PATH = "data/processed/fire_district.parquet"
FIRE_HISTORY_PATH = "data/processed/fire_history_lightweight.parquet"


def get_connection():
    return pymysql.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("MYSQL_EXPOSED_PORT", "3307")),
        user=os.environ["MYSQL_USER"],
        password=os.environ["MYSQL_PASSWORD"],
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        autocommit=False,
    )


def load_bpa(cursor):
    bpa = gpd.read_parquet(BPA_PATH)

    print(f"Loading BPA rows: {len(bpa)}")

    cursor.execute("DELETE FROM open_data_bpa")

    sql = """
        INSERT INTO open_data_bpa (
            lga_code,
            lga_name,
            geometry
        )
        VALUES (
            %s,
            %s,
            ST_GeomFromWKB(%s, 4326, 'axis-order=long-lat')
        )
    """

    rows = [
        (
            None if row.lga_code is None else str(row.lga_code),
            None if row.lga_name is None else str(row.lga_name),
            row.geometry.wkb,
        )
        for row in bpa.itertuples(index=False)
    ]

    cursor.executemany(sql, rows)


def load_fire_district(cursor):
    fire_district = gpd.read_parquet(FIRE_DISTRICT_PATH)

    print(f"Loading Fire District rows: {len(fire_district)}")

    cursor.execute("DELETE FROM open_data_fire_district")

    sql = """
        INSERT INTO open_data_fire_district (
            fire_district,
            geometry
        )
        VALUES (
            %s,
            ST_GeomFromWKB(%s, 4326, 'axis-order=long-lat')
        )
    """

    rows = [
        (
            str(row.fire_district),
            row.geometry.wkb,
        )
        for row in fire_district.itertuples(index=False)
    ]

    cursor.executemany(sql, rows)


def load_fire_history(cursor, batch_size=5000):
    fire_history = gpd.read_parquet(FIRE_HISTORY_PATH)

    print(f"Loading Historical Fire rows: {len(fire_history)}")

    cursor.execute("DELETE FROM open_data_fire_history")

    sql = """
        INSERT INTO open_data_fire_history (
            season,
            start_date,
            geometry
        )
        VALUES (
            %s,
            %s,
            ST_GeomFromWKB(%s, 4326, 'axis-order=long-lat')
        )
    """

    total = len(fire_history)

    for start in range(0, total, batch_size):
        batch = fire_history.iloc[start:start + batch_size]

        rows = []

        for row in batch.itertuples(index=False):
            season = None

            if not pd.isna(row.season):
                season = int(row.season)

            start_date = None

            if not pd.isna(row.start_date):
                start_date = pd.Timestamp(row.start_date).date()

            rows.append(
                (
                    season,
                    start_date,
                    row.geometry.wkb,
                )
            )

        cursor.executemany(sql, rows)

        print(
            f"Inserted Historical Fire rows: "
            f"{min(start + batch_size, total)}/{total}"
        )


def main():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            load_bpa(cursor)
            load_fire_district(cursor)
            load_fire_history(cursor)

        connection.commit()

        print("Open spatial data ingestion completed successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()