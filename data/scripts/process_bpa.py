import geopandas as gpd

# Load raw BPA shapefile
bpa = gpd.read_file("data/raw/bpa/BUSHFIRE_PRONE_AREA.shp")

print("Original shape:", bpa.shape)
print("Original CRS:", bpa.crs)

# Keep only the fields needed by the application
bpa_clean = bpa[
    ["LGA_CODE", "LGA_NAME", "geometry"]
].copy()

# Rename fields
bpa_clean = bpa_clean.rename(
    columns={
        "LGA_CODE": "lga_code",
        "LGA_NAME": "lga_name"
    }
)

# Convert to WGS84 so latitude/longitude can be used directly
bpa_clean = bpa_clean.to_crs("EPSG:4326")

# Check geometry quality
print("Missing geometries:", bpa_clean.geometry.isna().sum())
print("Invalid geometries:", (~bpa_clean.geometry.is_valid).sum())

# Repair invalid geometries if any exist
if (~bpa_clean.geometry.is_valid).any():
    bpa_clean["geometry"] = bpa_clean.geometry.make_valid()

print("\nProcessed shape:", bpa_clean.shape)
print("Processed CRS:", bpa_clean.crs)
print("Processed columns:", bpa_clean.columns.tolist())

print("\nSample:")
print(bpa_clean.head())



from shapely.geometry import Point


def check_bpa(latitude, longitude, bpa_gdf):
    point = Point(longitude, latitude)

    match = bpa_gdf[
        bpa_gdf.geometry.covers(point)
    ]

    return not match.empty


# Example test location
test_latitude = -38.16
test_longitude = 145.10

result = check_bpa(
    test_latitude,
    test_longitude,
    bpa_clean
)

print("\nTest location:")
print("Latitude:", test_latitude)
print("Longitude:", test_longitude)
print("Inside BPA:", result)


# Guaranteed test point inside the first BPA polygon
inside_point = bpa_clean.iloc[0].geometry.representative_point()

inside_latitude = inside_point.y
inside_longitude = inside_point.x

inside_result = check_bpa(
    inside_latitude,
    inside_longitude,
    bpa_clean
)

print("\nGuaranteed inside-BPA test:")
print("Latitude:", inside_latitude)
print("Longitude:", inside_longitude)
print("LGA:", bpa_clean.iloc[0]["lga_name"])
print("Inside BPA:", inside_result)


# Save processed BPA data as GeoParquet
output_path = "data/processed/bpa.parquet"

bpa_clean.to_parquet(
    output_path,
    index=False
)

print("\nSaved processed BPA data to:")
print(output_path)