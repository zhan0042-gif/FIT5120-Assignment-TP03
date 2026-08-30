# Data Processing

This directory contains open-data processing work for the FIT5120 project.

## Folder structure

- `raw/` — original datasets stored locally or in the team Google Drive and not committed to GitHub.
- `processed/` — cleaned and application-ready datasets committed to GitHub.
- `scripts/` — repeatable data cleaning and spatial-processing scripts.
- `test/` — spatial lookup test fixtures.

---

## Iteration 1

### 1. Designated Bushfire Prone Area (BPA)

#### Purpose

Determine whether a Victorian latitude and longitude falls inside a designated Bushfire Prone Area.

#### Source

Dataset: Designated Bushfire Prone Area (BPA)

Organisation: Department of Transport and Planning

Platform: Victorian Government DataVic

Source page:

https://discover.data.vic.gov.au/dataset/designated-bushfire-prone-area-bpa

Licence: Creative Commons Attribution 4.0 International

Published metadata record: 27/09/2023

Last updated: 30/07/2026

Update frequency: Unknown

The DataVic metadata notes that the latest listed BPA review was gazetted on 16 June 2026.

#### Raw data

Original shapefile components are stored outside GitHub in the team data storage.

Main raw file:

`raw/bpa/BUSHFIRE_PRONE_AREA.shp`

Raw data is excluded from Git using:

`data/raw/`

#### Processed output

`processed/bpa.parquet`

#### Processing

Processing is performed by:

`scripts/process_bpa.py`

The script:

- loads the original BPA shapefile
- keeps only fields required by the application
- renames fields to consistent lowercase names
- converts the CRS to EPSG:4326
- validates geometries
- provides a point-in-polygon BPA lookup
- exports the result as GeoParquet

#### Processed fields

| Field | Description |
|---|---|
| `lga_code` | Local Government Area code from the source dataset |
| `lga_name` | Local Government Area name |
| `geometry` | BPA polygon geometry |

#### CRS

`EPSG:4326`

#### Lookup result

Given:

~~~text
latitude
longitude
~~~

the lookup returns:

~~~text
is_bushfire_prone_area: true/false
~~~

#### Limitations

BPA designation is used only to determine whether a location falls inside an officially designated Bushfire Prone Area.

It must not be interpreted as a personalised bushfire risk score or prediction.

---

### 2. CFA Fire District

#### Purpose

Determine the CFA Total Fire Ban / Fire Weather District associated with a Victorian latitude and longitude.

This allows the Backend to associate a household location with the correct CFA district before retrieving live or forecast Fire Danger Rating information.

#### Source

Dataset: Vicmap Admin - Country Fire Authority (CFA) Total Fire Ban District Polygon

Organisation: Country Fire Authority

Platform: Victorian Government DataVic

Source page:

https://discover.data.vic.gov.au/dataset/vicmap-admin-country-fire-authority-cfa-total-fire-ban-district-polygon

Licence: Creative Commons Attribution 4.0 International

Published metadata record: 28/02/2025

Last updated: 30/07/2026

Update frequency: Unknown

#### Raw data

Main raw file:

`raw/fire_district/CFA_TFB_DISTRICT.shp`

Original shapefile components are stored outside GitHub.

#### Processed output

`processed/fire_district.parquet`

#### Processing

Processing is performed by:

`scripts/process_fire_district.py`

The script:

- loads the original CFA district shapefile
- keeps the district name and geometry
- renames the district field to `fire_district`
- converts the CRS to EPSG:4326
- validates geometries
- standardises district names
- provides a point-in-polygon district lookup
- exports the result as GeoParquet

#### Processed fields

| Field | Description |
|---|---|
| `fire_district` | CFA fire weather / Total Fire Ban district |
| `geometry` | District polygon geometry |

#### CFA districts

The processed dataset contains nine districts:

- Central
- Northern Country
- North Central
- Wimmera
- North East
- East Gippsland
- South West
- Mallee
- West and South Gippsland

#### CRS

`EPSG:4326`

#### Lookup result

Given:

~~~text
latitude
longitude
~~~

the lookup returns the corresponding CFA district, for example:

~~~text
fire_district: Central
~~~

If a point is not inside a district polygon, the lookup returns `None`.

#### Limitations

This dataset identifies the CFA district only.

It does not calculate Fire Danger Ratings or Total Fire Ban status.

Live and forecast Fire Danger Rating information must be retrieved separately from an official CFA or Bureau of Meteorology source by the Backend.

---

### 3. Combined Spatial Lookup

Combined lookup testing is implemented in:

`scripts/test_spatial_lookup.py`

For a latitude and longitude, the current data layer can return:

~~~json
{
  "location": {
    "latitude": -37.89002627699995,
    "longitude": 144.12595975369607
  },
  "is_bushfire_prone_area": true,
  "fire_district": "Central"
}
~~~

This is the main Iteration 1 spatial data output intended for Backend integration.

The lookup combines:

- Designated Bushfire Prone Area status
- CFA Fire District

into a single location context result.

---

### 4. Spatial Test Fixtures

Test locations are stored in:

`test/location_test_cases.csv`

The current fixture set contains eight test locations across multiple CFA districts.

The fixtures include both:

~~~text
BPA = True
BPA = False
~~~

The fixtures are validated using:

`scripts/test_spatial_lookup.py`

Each fixture checks:

- expected BPA status
- expected CFA fire district

The current fixtures cover:

- Central
- Northern Country
- East Gippsland
- Mallee

Each of these districts contains one BPA-positive and one BPA-negative test case.

The test coordinates are derived from the processed official spatial datasets rather than manually guessed locations.

---

## Data Handling

Large original GIS datasets are not committed to GitHub.

The project follows this convention:

~~~text
Raw/original datasets
        ↓
Local storage / team Google Drive

Processing scripts
        ↓
GitHub

Processed application-ready datasets
        ↓
GitHub where file size is reasonable
~~~

GeoParquet is used for processed geospatial datasets because it preserves spatial geometry and CRS information while providing a portable application-ready format.

---

## Iteration 1 Data Flow

The current spatial data workflow is:

~~~text
Official Victorian open datasets
        ↓
Raw shapefiles
        ↓
Python / GeoPandas processing
        ↓
Geometry validation
        ↓
CRS conversion to EPSG:4326
        ↓
Processed GeoParquet files
        ↓
Spatial point-in-polygon lookup
        ↓
BPA status + CFA Fire District
        ↓
Backend integration
~~~

The Backend can then use the returned CFA district to retrieve current or forecast Fire Danger Rating information from an official live source.

The Data layer does not calculate or predict official Fire Danger Ratings.

---

## Current Processed Outputs

| Dataset | Processed file | Purpose |
|---|---|---|
| Bushfire Prone Area | `processed/bpa.parquet` | Determine whether a location is inside a designated BPA |
| CFA Fire District | `processed/fire_district.parquet` | Determine the CFA fire district for a location |

---

## Current Scripts

| Script | Purpose |
|---|---|
| `scripts/process_bpa.py` | Clean, validate and export BPA spatial data |
| `scripts/process_fire_district.py` | Clean, validate and export CFA Fire District data |
| `scripts/test_spatial_lookup.py` | Test combined BPA and Fire District spatial lookups |

---

## Current Test Data

| File | Purpose |
|---|---|
| `test/location_test_cases.csv` | Stable location fixtures for validating BPA and Fire District lookups |

---

## Important Data Interpretation Notes

The processed datasets provide location context only.

They must not be used to create unsupported or unvalidated personalised bushfire risk predictions.

In particular:

- BPA status is an official designation, not a personalised risk score.
- CFA Fire District identifies the relevant district, not the current Fire Danger Rating.
- Fire Danger Ratings must come from an official live or forecast source.
- Environmental or historical datasets added later should be presented as contextual information unless a validated methodology supports stronger interpretation.


---

## Fire History Context

### Purpose

The Fire History dataset is used to provide simple historical bushfire context around a household location for Iteration 1 US2.2.

The Fire History functionality is contextual only. It does not calculate, estimate or predict personalised bushfire risk.

### Source processing

The original Fire History dataset contains several fire types.

The processing pipeline keeps only records where:

~~~text
FIRETYPE = Bushfire
~~~

This prevents planned burns and other fire types from being mixed with historical bushfire context.

Processing is performed by:

`scripts/process_fire_history.py`

The full processed dataset contains:

~~~text
628,308 Bushfire records
~~~

covering seasons from:

~~~text
1903 to 2025
~~~

The full processed dataset is converted to:

`EPSG:4326`

and stored as:

`processed/fire_history.parquet`

### Full processed dataset storage

The full processed Fire History GeoParquet is approximately 639 MB.

Because of its size, it is not committed to GitHub.

It is stored separately in the team's shared Google Drive / data storage.

The file is excluded from Git using:

~~~text
data/processed/fire_history.parquet
~~~

The processing script remains in GitHub so that the full processed dataset can be reproduced from the original source.

### Lightweight Backend dataset

To support faster Backend integration, a lightweight Fire History dataset is derived from the full processed dataset.

The lightweight dataset is created by:

`scripts/create_fire_history_lightweight.py`

The output is:

`processed/fire_history_lightweight.parquet`

The lightweight file is approximately 11 MB.

It keeps all 628,308 Bushfire records but retains only:

- `season`
- `start_date`
- `geometry`

The original fire polygon geometry is replaced with one representative point located inside each original fire polygon.

This significantly reduces storage size while preserving one spatial reference point for every historical Bushfire record.

The full polygon dataset remains preserved separately and is not replaced by the lightweight dataset.

### Lightweight lookup

The application-facing lookup is implemented in:

`scripts/fire_history_lookup.py`

The lookup accepts:

~~~text
latitude
longitude
search_radius_km
~~~

The current default search radius is:

~~~text
20 km
~~~

The lookup returns a compact result such as:

~~~json
{
  "historical_fire_record_count": 58,
  "last_recorded_burn_year": 2025,
  "most_recent_fire_date": "2025-02-03",
  "search_radius_km": 20
}
~~~

The exact values depend on the location being queried.

### Lookup method

The lightweight lookup:

1. loads the representative-point Fire History dataset
2. receives a latitude and longitude in EPSG:4326
3. transforms the query location and representative points to EPSG:7899 (GDA2020 / Vicgrid)
4. creates a search area using the specified radius in kilometres
5. uses a spatial index to identify representative points that fall inside the search area
6. derives a compact contextual response from the matching records

### Approximation and interpretation

The lightweight dataset uses a representative point for each original historical fire polygon.

Therefore:

`historical_fire_record_count`

represents the number of historical Bushfire record representative points located inside the selected search radius.

It is not exactly equivalent to counting all original fire polygons that intersect the search area.

For example, a large historical fire polygon may intersect the search radius even if its representative point lies outside the radius.

The full polygon dataset is retained separately when exact polygon-level spatial analysis is required.

The lightweight result is designed for fast contextual display in the application.

It must not automatically be interpreted as the number of unique real-world bushfire events because a fire event may be represented by more than one spatial record.

`last_recorded_burn_year` represents the most recent recorded fire season among matching historical records.

`most_recent_fire_date` represents the latest available `START_DATE` among matching records.

`search_radius_km` makes the geographic scope of the lookup explicit.

These values provide historical context only.

They must not be used to claim that:

- a future bushfire will occur
- a location is safe or unsafe
- a household has a particular bushfire risk level
- historical fire frequency directly predicts future fire activity


---

## Backend Handoff

The main reusable location-context module for Backend integration is:

`data/scripts/location_context.py`

It combines the current Iteration 1 spatial context into one application-ready response:

~~~json
{
  "location": {
    "latitude": -37.89002627699995,
    "longitude": 144.12595975369607
  },
  "is_bushfire_prone_area": true,
  "fire_district": "Central",
  "environmental_context": {
    "fire_history": {
      "historical_fire_record_count": 58,
      "last_recorded_burn_year": 2025,
      "most_recent_fire_date": "2025-02-03",
      "search_radius_km": 20
    }
  }
}
~~~

Backend can import:

~~~python
from location_context import get_location_context
~~~

and call:

~~~python
result = get_location_context(
    latitude,
    longitude
)
~~~

The current response includes:

- Designated Bushfire Prone Area status
- CFA Fire District
- historical bushfire context

The Fire History component is contextual only and must not be treated as a personalised bushfire risk score.

Validation for the combined response is implemented in:

`data/scripts/test_location_context.py`

Broader spatial fixture validation remains in:

`data/scripts/test_spatial_lookup.py`