import geopandas as gpd


# Load raw Fire History shapefile
fire_history = gpd.read_file(
    "data/raw/fire_history/FIRE_HISTORY.shp"
)

print("Original shape:", fire_history.shape)
print("Original CRS:", fire_history.crs)


# --------------------------------------------------
# 1. Keep Bushfire records only
# --------------------------------------------------

fire_history_clean = fire_history[
    fire_history["FIRETYPE"] == "Bushfire"
].copy()

print("\nBushfire-only shape:", fire_history_clean.shape)


# --------------------------------------------------
# 2. Keep only fields useful to the application
# --------------------------------------------------

fire_history_clean = fire_history_clean[
    [
        "SEASON",
        "FIRE_NO",
        "NAME",
        "START_DATE",
        "AREA_HA",
        "REGION",
        "geometry"
    ]
].copy()


# --------------------------------------------------
# 3. Rename fields
# --------------------------------------------------

fire_history_clean = fire_history_clean.rename(
    columns={
        "SEASON": "season",
        "FIRE_NO": "fire_no",
        "NAME": "fire_name",
        "START_DATE": "start_date",
        "AREA_HA": "area_ha",
        "REGION": "region"
    }
)


# --------------------------------------------------
# 4. Convert CRS to WGS84
# --------------------------------------------------

fire_history_clean = fire_history_clean.to_crs(
    "EPSG:4326"
)


# --------------------------------------------------
# 5. Check geometry quality
# --------------------------------------------------

print(
    "\nMissing geometries:",
    fire_history_clean.geometry.isna().sum()
)

print(
    "Invalid geometries:",
    (~fire_history_clean.geometry.is_valid).sum()
)

if (~fire_history_clean.geometry.is_valid).any():
    fire_history_clean["geometry"] = (
        fire_history_clean.geometry.make_valid()
    )


# --------------------------------------------------
# 6. Inspect cleaned data
# --------------------------------------------------

print("\nProcessed shape:", fire_history_clean.shape)
print("Processed CRS:", fire_history_clean.crs)
print("Processed columns:", fire_history_clean.columns.tolist())

print("\nSeason range:")
print(
    fire_history_clean["season"].min(),
    "-",
    fire_history_clean["season"].max()
)

print("\nMissing values:")
print(fire_history_clean.isna().sum())

print("\nSample:")
print(fire_history_clean.head())


# --------------------------------------------------
# 7. Save processed GeoParquet
# --------------------------------------------------

output_path = "data/processed/fire_history.parquet"

fire_history_clean.to_parquet(
    output_path,
    index=False
)

print("\nSaved processed Fire History data to:")
print(output_path)