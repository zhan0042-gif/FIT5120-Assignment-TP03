import os

import pandas as pd
import pymysql


FDR_HISTORY_PATH = "data/processed/fdr_history.parquet"


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


def load_fdr_history(cursor):
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
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            load_fdr_history(cursor)

        connection.commit()

        print("FDR History ingestion completed successfully.")

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    main()