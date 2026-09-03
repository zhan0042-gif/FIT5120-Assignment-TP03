"""
Process the Victorian Bushfire Prone Area (BPA) spatial dataset.

This script cleans and standardises the raw BPA shapefile, converts the
geometry to EPSG:4326, validates the geometry, tests BPA point lookup,
and saves the processed dataset as GeoParquet.
"""


import geopandas as gpd
from shapely.geometry import Point

# Load the official raw Victorian BPA shapefile
bpa = gpd.read_file("data/raw/bpa/BUSHFIRE_PRONE_AREA.shp")

print("Original shape:", bpa.shape)
print("Original CRS:", bpa.crs)

# Keep only the fields needed by the application
bpa_clean = bpa[
    ["LGA_CODE", "LGA_NAME", "geometry"]
].copy()

#  Rename source fields to consistent, application-friendly lowercase names
bpa_clean = bpa_clean.rename(
    columns={
        "LGA_CODE": "lga_code",
        "LGA_NAME": "lga_name"
    }
)

# Convert geometry to WGS84 (EPSG:4326) to match application latitude/longitude coordinates
bpa_clean = bpa_clean.to_crs("EPSG:4326")

# Check for missing or invalid polygon geometries before spatial lookup
print("Missing geometries:", bpa_clean.geometry.isna().sum())
print("Invalid geometries:", (~bpa_clean.geometry.is_valid).sum())

# Repair invalid geometries, if any, so point-in-polygon operations remain reliable
if (~bpa_clean.geometry.is_valid).any():
    bpa_clean["geometry"] = bpa_clean.geometry.make_valid()

print("\nProcessed shape:", bpa_clean.shape)
print("Processed CRS:", bpa_clean.crs)
print("Processed columns:", bpa_clean.columns.tolist())

print("\nSample:")
print(bpa_clean.head())



def check_bpa(latitude, longitude, bpa_gdf):
    """
    Check whether a geographic location is inside a Bushfire Prone Area (BPA).

    Parameters:
        latitude (float): Latitude of the location to check.
        longitude (float): Longitude of the location to check.
        bpa_gdf (GeoDataFrame): Processed BPA polygon dataset in EPSG:4326.

    Returns:
        bool: True if the location is inside or on the boundary of a BPA polygon;
              otherwise False.
    """

    # Shapely Point uses (x, y), so longitude is passed before latitude     
    point = Point(longitude, latitude)

    # Find BPA polygons that contain or cover the location point
    match = bpa_gdf[
        bpa_gdf.geometry.covers(point)
    ]

    # If at least one polygon matches, the location is considered inside a BPA
    return not match.empty


# Test the lookup using an example latitude/longitude location
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


# Generate a point guaranteed to lie inside the first BPA polygon for validation
inside_point = bpa_clean.iloc[0].geometry.representative_point()

# Extract latitude (y) and longitude (x) from the generated point
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


# Save the cleaned BPA dataset as GeoParquet for efficient application use
output_path = "data/processed/bpa.parquet"

bpa_clean.to_parquet(
    output_path,
    index=False
)

print("\nSaved processed BPA data to:")
print(output_path)