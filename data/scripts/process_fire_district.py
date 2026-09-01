import geopandas as gpd
from shapely.geometry import Point

# Load raw CFA Fire District shapefile
fire_district = gpd.read_file(
    "data/raw/fire_district/CFA_TFB_DISTRICT.shp"
)

print("Original shape:", fire_district.shape)
print("Original CRS:", fire_district.crs)

# Keep only fields needed by the application
fire_district_clean = fire_district[
    ["TFB_DIST", "geometry"]
].copy()

# Rename field
fire_district_clean = fire_district_clean.rename(
    columns={
        "TFB_DIST": "fire_district"
    }
)

# Convert to WGS84 for latitude/longitude lookup
fire_district_clean = fire_district_clean.to_crs("EPSG:4326")

# Standardise district names
fire_district_clean["fire_district"] = (
    fire_district_clean["fire_district"]
    .str.strip()
    .str.title()
    .str.replace(" And ", " and ", regex=False)
)

# Check geometry quality
print("Missing geometries:", fire_district_clean.geometry.isna().sum())
print("Invalid geometries:", (~fire_district_clean.geometry.is_valid).sum())

if (~fire_district_clean.geometry.is_valid).any():
    fire_district_clean["geometry"] = (
        fire_district_clean.geometry.make_valid()
    )

print("\nProcessed shape:", fire_district_clean.shape)
print("Processed CRS:", fire_district_clean.crs)
print("Processed columns:", fire_district_clean.columns.tolist())

print("\nDistrict values:")
print(fire_district_clean["fire_district"].tolist())


def get_fire_district(latitude, longitude, district_gdf):
    point = Point(longitude, latitude)

    match = district_gdf[
        district_gdf.geometry.covers(point)
    ]

    if match.empty:
        return None

    return match.iloc[0]["fire_district"]


# Guaranteed test point inside first fire district
test_point = (
    fire_district_clean.iloc[0]
    .geometry
    .representative_point()
)

test_latitude = test_point.y
test_longitude = test_point.x

result = get_fire_district(
    test_latitude,
    test_longitude,
    fire_district_clean
)

print("\nGuaranteed district test:")
print("Latitude:", test_latitude)
print("Longitude:", test_longitude)
print("Expected district:", fire_district_clean.iloc[0]["fire_district"])
print("Returned district:", result)


# Save processed Fire District data as GeoParquet
output_path = "data/processed/fire_district.parquet"

fire_district_clean.to_parquet(
    output_path,
    index=False
)

print("\nSaved processed Fire District data to:")
print(output_path)