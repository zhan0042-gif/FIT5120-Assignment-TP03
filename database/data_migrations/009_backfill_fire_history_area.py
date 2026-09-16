"""Reload only Historical Fire rows so migration 009 receives area_ha values."""

from pathlib import Path


REQUIRES_SCHEMA = "009_add_fire_history_area_ha.sql"
SOURCE_PATH = Path("data/processed/fire_history_lightweight.parquet")
BATCH_SIZE = 5_000


def run(connection) -> None:
    import pyarrow.parquet as parquet

    source = parquet.ParquetFile(SOURCE_PATH)
    required_columns = {"season", "start_date", "area_ha", "geometry"}
    available_columns = set(source.schema_arrow.names)
    missing_columns = required_columns - available_columns
    if missing_columns:
        raise RuntimeError(
            "Historical Fire parquet is missing required columns: "
            + ", ".join(sorted(missing_columns))
        )

    print(f"Reloading Historical Fire rows: {source.metadata.num_rows}")
    insert_sql = """
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

    inserted = 0
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM open_data_fire_history")
        for batch in source.iter_batches(
            batch_size=BATCH_SIZE,
            columns=["season", "start_date", "area_ha", "geometry"],
        ):
            columns = batch.to_pydict()
            rows = []
            for season, start_date, area_ha, geometry in zip(
                columns["season"],
                columns["start_date"],
                columns["area_ha"],
                columns["geometry"],
                strict=True,
            ):
                rows.append(
                    (
                        int(season) if season is not None else None,
                        start_date.date() if start_date is not None else None,
                        float(area_ha) if area_ha is not None else None,
                        geometry,
                    )
                )
            cursor.executemany(insert_sql, rows)
            inserted += len(rows)
            print(f"Inserted Historical Fire rows: {inserted}/{source.metadata.num_rows}")

        cursor.execute(
            """
            SELECT
                COUNT(*) AS total_rows,
                SUM(area_ha IS NULL) AS missing_area_rows
            FROM open_data_fire_history
            """
        )
        total_rows, missing_area_rows = cursor.fetchone()

    total_rows = int(total_rows)
    missing_area_rows = int(missing_area_rows or 0)
    print(
        "Historical Fire verification: "
        f"total_rows={total_rows}, missing_area_rows={missing_area_rows}"
    )
    if total_rows == 0:
        raise RuntimeError("Historical Fire backfill produced zero rows")
    if missing_area_rows != 0:
        raise RuntimeError(
            "Historical Fire backfill left rows without area_ha: "
            f"{missing_area_rows}"
        )
