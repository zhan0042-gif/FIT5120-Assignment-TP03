import geopandas as gpd


# --------------------------------------------------
# Load full processed Fire History dataset
# --------------------------------------------------

input_path = "data/processed/fire_history.parquet"

fire_history = gpd.read_parquet(input_path)

print("Original records:", len(fire_history))
print("Original CRS:", fire_history.crs)


# --------------------------------------------------
# Keep only fields needed for Backend context
# --------------------------------------------------

fire_light = fire_history[
    [
        "season",
        "start_date",
        "geometry"
    ]
].copy()


# --------------------------------------------------
# Convert polygons to representative points
#
# representative_point() guarantees the generated
# point lies inside the original polygon.
# --------------------------------------------------

print("\nCreating representative points...")

fire_light["geometry"] = (
    fire_light.geometry.representative_point()
)


# --------------------------------------------------
# Check result
# --------------------------------------------------

print("Records after conversion:", len(fire_light))

print(
    "Geometry types:",
    fire_light.geometry.geom_type.value_counts().to_dict()
)

print(
    "Missing geometries:",
    fire_light.geometry.isna().sum()
)

print(
    "Season range:",
    fire_light["season"].min(),
    "-",
    fire_light["season"].max()
)


# --------------------------------------------------
# Save lightweight GeoParquet
# --------------------------------------------------

output_path = (
    "data/processed/fire_history_lightweight.parquet"
)

fire_light.to_parquet(
    output_path,
    index=False
)

print("\nSaved lightweight Fire History data to:")
print(output_path)