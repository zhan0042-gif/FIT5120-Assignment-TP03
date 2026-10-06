from pathlib import Path

import pandas as pd


RAW_PATH = Path("data/raw/FDR_history/FDRhistory_AFDRS.csv")
OUTPUT_PATH = Path("data/processed/fdr_history.parquet")

DISTRICTS = [
    "Mallee",
    "Wimmera",
    "South West",
    "Northern Country",
    "North Central",
    "Central",
    "North East",
    "South and West Gippsland",
    "East Gippsland",
]

RATING_LABELS = {
    0: "No rating",
    1: "Moderate",
    2: "High",
    3: "Extreme",
    4: "Catastrophic",
}


def main():
    print(f"Reading: {RAW_PATH}")

    df = pd.read_csv(RAW_PATH)

    print(f"Raw rows: {len(df)}")

    # Parse issue timestamp so updates can be ordered correctly.
    df["issued_at"] = pd.to_datetime(
        df["Date"] + " " + df["Time"],
        format="%Y-%m-%d %H:%M",
        errors="coerce",
    )

    if df["issued_at"].isna().any():
        raise ValueError("Some Date/Time values could not be parsed.")

    # Keep the latest FDR update issued for each date.
    latest = (
        df.sort_values("issued_at")
        .groupby("Date", as_index=False)
        .tail(1)
        .copy()
    )

    print(f"Daily latest records: {len(latest)}")

    # Convert wide district columns into one row per date/district.
    cleaned = latest.melt(
        id_vars=["Date", "issued_at"],
        value_vars=DISTRICTS,
        var_name="district",
        value_name="rating_code",
    )

    cleaned = cleaned.rename(columns={"Date": "date"})

    cleaned["date"] = pd.to_datetime(cleaned["date"]).dt.date
    cleaned["rating_code"] = cleaned["rating_code"].astype(int)

    # Validate AFDRS codes.
    valid_codes = set(RATING_LABELS)
    found_codes = set(cleaned["rating_code"].unique())

    invalid_codes = found_codes - valid_codes

    if invalid_codes:
        raise ValueError(
            f"Unexpected AFDRS rating codes found: {invalid_codes}"
        )

    cleaned["rating_label"] = cleaned["rating_code"].map(RATING_LABELS)

    # Useful derived fields for later analysis / ML.
    cleaned["year"] = pd.to_datetime(cleaned["date"]).dt.year
    cleaned["month"] = pd.to_datetime(cleaned["date"]).dt.month
    cleaned["day_of_year"] = pd.to_datetime(cleaned["date"]).dt.dayofyear

    cleaned = cleaned[
        [
            "date",
            "issued_at",
            "district",
            "rating_code",
            "rating_label",
            "year",
            "month",
            "day_of_year",
        ]
    ].sort_values(["date", "district"])

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    cleaned.to_parquet(
        OUTPUT_PATH,
        index=False,
    )

    print(f"\nSaved: {OUTPUT_PATH}")
    print(f"Processed rows: {len(cleaned)}")

    print("\nRating distribution:")
    print(cleaned["rating_label"].value_counts())

    print("\nFirst 10 rows:")
    print(cleaned.head(10))


if __name__ == "__main__":
    main()