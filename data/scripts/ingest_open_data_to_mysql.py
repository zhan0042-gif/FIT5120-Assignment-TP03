"""
Load processed FIREBREAK Open Data into MySQL.

This script ingests:
- Bushfire Prone Area polygons
- CFA Fire District polygons
- lightweight Historical Fire representative points
- Australian Fire Danger Rating System history

The processed files remain the reproducible application-ready data artifacts,
while MySQL becomes the runtime storage used by Backend.
"""

import os

import geopandas as gpd
import pandas as pd
import pymysql


BPA_PATH = "data/processed/bpa.parquet"
FIRE_DISTRICT_PATH = "data/processed/fire_district.parquet"
FIRE_HISTORY_PATH = "data/processed/fire_history_lightweight.parquet"
FDR_HISTORY_PATH = "data/processed/fdr_history.parquet"


def get_connection():
    """
    Create a MySQL connection for the Open Data ingestion process.

    Connection settings are read from environment variables. This ingestion
    script is normally run from the host machine, so MYSQL_EXPOSED_PORT is used
    for the host-accessible Docker MySQL port.

    Returns:
        pymysql.connections.Connection:
            A MySQL connection with transactions enabled.
    """
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
    """
    Load the processed Bushfire Prone Area dataset into MySQL.

    The existing rows in open_data_bpa are removed before the processed
    GeoParquet records are inserted.

    Args:
        cursor:
            Active PyMySQL cursor used to execute database statements.

    Returns:
        None.
    """
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
    """
    Load the processed CFA Fire District dataset into MySQL.

    The existing rows in open_data_fire_district are removed before the
    processed district polygons are inserted.

    Args:
        cursor:
            Active PyMySQL cursor used to execute database statements.

    Returns:
        None.
    """
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
    """
    Load the lightweight Historical Fire dataset into MySQL in batches.

    The lightweight dataset contains one representative point for each
    historical bushfire record. Existing rows are removed before reloading.

    Args:
        cursor:
            Active PyMySQL cursor used to execute database statements.
        batch_size:
            Maximum number of Historical Fire rows inserted per batch.
            Defaults to 5000.

    Returns:
        None.
    """
    fire_history = gpd.read_parquet(FIRE_HISTORY_PATH)

    print(f"Loading Historical Fire rows: {len(fire_history)}")

    cursor.execute("DELETE FROM open_data_fire_history")

    sql = """
        INSERT INTO open_data_fire_history (
            season,
            start_date,
            area_ha,
            geometry
        )
        VALUES (
            %s,
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

            area_ha = None

            if not pd.isna(row.area_ha):
                area_ha = float(row.area_ha)

            rows.append(
                (
                    season,
                    start_date,
                    area_ha,
                    row.geometry.wkb,
                )
            )

        cursor.executemany(sql, rows)

        print(
            f"Inserted Historical Fire rows: "
            f"{min(start + batch_size, total)}/{total}"
        )

def load_fdr_history(cursor):
    """
    Load the processed AFDRS Fire Danger Rating history into MySQL.

    The processed dataset contains one latest rating per date and fire
    weather district. Existing rows are removed before reloading.

    Args:
        cursor:
            Active PyMySQL cursor.

    Returns:
        None.
    """
    fdr_history = pd.read_parquet(FDR_HISTORY_PATH)

    print(f"Loading FDR History rows: {len(fdr_history)}")

    cursor.execute("DELETE FROM open_data_fdr_history")

    sql = """
        INSERT INTO open_data_fdr_history (
            date,
            issued_at,
            district,
            rating_code,
            rating_label,
            year,
            month,
            day_of_year
        )
        VALUES (
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s,
            %s
        )
    """

    rows = [
        (
            pd.Timestamp(row.date).date(),
            pd.Timestamp(row.issued_at).to_pydatetime(),
            str(row.district),
            int(row.rating_code),
            str(row.rating_label),
            int(row.year),
            int(row.month),
            int(row.day_of_year),
        )
        for row in fdr_history.itertuples(index=False)
    ]

    cursor.executemany(sql, rows)


def main():
    """
    Run the complete Open Data ingestion process.

    BPA, CFA Fire District, lightweight Historical Fire, and FDR History data are loaded
    inside one transaction. The transaction is committed when all loaders
    succeed and rolled back if any loader fails.

    Returns:
        None.
    """
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            load_bpa(cursor)
            load_fire_district(cursor)
            load_fire_history(cursor)
            load_fdr_history(cursor)

        connection.commit()

        print("Open spatial data ingestion completed successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()
