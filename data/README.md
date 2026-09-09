# Data Processing

This directory contains open-data processing and spatial lookup work for the FIT5120 FIREBREAK project.

See [`docs/iteration1-integration-contract.md`](../docs/iteration1-integration-contract.md)
for the Backend adapter, runtime modes, and complete cross-component contract.

This README remains the source for datasets, processing, provenance, ingestion,
and spatial lookup details.

Install the dedicated Data tooling dependencies before running processing,
GeoParquet validation, or ingestion scripts:

```bash
python -m pip install -r data/requirements.txt
```

Normal Backend runtime uses `backend/requirements.txt` instead and does not
install GeoPandas or PyArrow.

## Folder structure

- `raw/` — original datasets stored locally or in the team Google Drive and not committed to GitHub.
- `processed/` — cleaned and application-ready datasets committed to GitHub where file size permits.
- `scripts/` — repeatable data cleaning, ingestion, and spatial lookup scripts.
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
- exports the result as GeoParquet

#### Processed fields

| Field | Description |
|---|---|
| `lga_code` | Local Government Area code from the source dataset |
| `lga_name` | Local Government Area name |
| `geometry` | BPA polygon geometry |

#### CRS

`EPSG:4326`

#### Runtime lookup result

Given:

~~~text
latitude
longitude
~~~

the lookup returns:

~~~text
is_bushfire_prone_area: true/false
~~~

The processed polygon data is ingested into MySQL and queried at runtime through
`scripts/open_data_mysql.py`.

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

#### Runtime lookup result

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

The processed polygons are stored in MySQL for runtime lookup.

#### Limitations

This dataset identifies the CFA district only.

It does not calculate Fire Danger Ratings or Total Fire Ban status.

Live and forecast Fire Danger Rating information must be retrieved separately from an official CFA or Bureau of Meteorology source by the Backend.

---

### 3. Combined Spatial Lookup

Combined lookup testing is implemented in:

`scripts/test_spatial_lookup.py`

For a latitude and longitude, the application-facing result includes:

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

The combined lookup is implemented by:

`data/scripts/location_context.py`

The implementation obtains BPA, CFA Fire District, and Historical Fire context
from MySQL through:

`data/scripts/open_data_mysql.py`

The response contract used by Backend remains unchanged from the previous
GeoParquet-backed implementation.

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
- Fire History response structure
- Fire History record count validity
- configured search radius

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
        ↓
MySQL ingestion for runtime use
~~~

GeoParquet remains the reproducible processed-data format because it preserves
spatial geometry and CRS information while providing portable application-ready
artifacts.

MySQL is the runtime storage layer for the three spatial datasets currently used
by the Backend.

---

## Iteration 1 Data Flow

The current spatial data workflow is:

~~~text
Official Victorian Open Data
        ↓
Raw shapefiles
        ↓
Python / GeoPandas processing
        ↓
Geometry validation
        ↓
CRS conversion to EPSG:4326
        ↓
Processed GeoParquet
        ↓
ingest_open_data_to_mysql.py
        ↓
MySQL spatial Open Data tables
        ↓
open_data_mysql.py
        ↓
location_context.py
        ↓
Backend DataSpatialProvider
        ↓
Local context API
        ↓
Frontend Overview
~~~

The Backend can use the returned CFA district to retrieve current or forecast
Fire Danger Rating information from an official live source.

The Data layer does not calculate or predict official Fire Danger Ratings.

---

## Runtime Storage Boundary

Processed GeoParquet files remain the reproducible application-ready artifacts
produced by the Data pipeline.

The following processed datasets are ingested into MySQL for Backend runtime use:

- Bushfire Prone Area
- CFA Fire District
- lightweight Historical Fire

The MySQL tables are:

~~~text
open_data_bpa
open_data_fire_district
open_data_fire_history
~~~

The ingestion is performed by:

`data/scripts/ingest_open_data_to_mysql.py`

Runtime spatial queries are implemented in:

`data/scripts/open_data_mysql.py`

The Backend therefore no longer needs to load the BPA, CFA Fire District, or
lightweight Historical Fire GeoParquet datasets into memory for normal runtime
lookups.

The existing table:

`household_location_context`

has a different purpose. It stores a small derived per-household snapshot of
location context and is invalidated when the saved household location changes.
It is refreshed after 24 hours by default; deployments can configure
`APP_SPATIAL_CACHE_MAX_AGE_HOURS`.

It is not a copy of the Open Data tables.

Vicmap is used separately for address suggestions and verification.

BOM weather and Fire Danger Rating are dynamic official-provider data and are
not stored in the spatial Open Data tables.

---

## Current Processed Outputs

| Dataset | Processed file | Purpose |
|---|---|---|
| Bushfire Prone Area | `processed/bpa.parquet` | Determine whether a location is inside a designated BPA |
| CFA Fire District | `processed/fire_district.parquet` | Determine the CFA fire district for a location |
| Lightweight Fire History | `processed/fire_history_lightweight.parquet` | Provide contextual historical-fire records within a configured radius |
| Full Fire History | `processed/fire_history.parquet` | Preserve full cleaned historical-fire polygon geometry for detailed analysis |

The full Fire History file is approximately 639 MB and is stored separately in
team shared storage rather than GitHub.

---

## Current Scripts

| Script | Purpose |
|---|---|
| `scripts/process_bpa.py` | Clean, validate, and export BPA spatial data |
| `scripts/process_fire_district.py` | Clean, validate, and export CFA Fire District data |
| `scripts/process_fire_history.py` | Clean and export the full bushfire-history dataset |
| `scripts/create_fire_history_lightweight.py` | Create the representative-point Historical Fire dataset |
| `scripts/ingest_open_data_to_mysql.py` | Ingest processed BPA, CFA District, and lightweight Historical Fire data into MySQL |
| `scripts/open_data_mysql.py` | Perform MySQL-backed runtime spatial lookups |
| `scripts/location_context.py` | Combine BPA, district, and Historical Fire results for Backend |
| `scripts/fire_history_lookup.py` | Previous GeoParquet-based Historical Fire lookup retained for validation/comparison |
| `scripts/test_location_context.py` | Validate the combined application-facing response |
| `scripts/test_spatial_lookup.py` | Validate BPA/district fixtures and Fire History response structure |

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
- Historical fire information is contextual only.
- Historical fire frequency must not be treated as a prediction of future fire activity.

---

## Fire History Context

### Purpose

The Fire History dataset is used to provide simple historical bushfire context around a household location for Iteration 1 US2.2.

The Fire History functionality is contextual only.

It does not calculate, estimate, or predict personalised bushfire risk.

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

### Lightweight runtime dataset

A lightweight Historical Fire dataset is derived from the full processed dataset.

The lightweight dataset is created by:

`scripts/create_fire_history_lightweight.py`

The output is:

`processed/fire_history_lightweight.parquet`

The lightweight file is approximately 11 MB.

It keeps all 628,308 Bushfire records but retains only:

- `season`
- `start_date`
- `geometry`

The original fire polygon geometry is replaced with one representative point
located inside each original fire polygon.

This significantly reduces storage size while preserving one spatial reference
point for every Historical Fire record.

The full polygon dataset remains preserved separately and is not replaced by
the lightweight dataset.

### MySQL ingestion

The lightweight dataset is the Historical Fire dataset currently ingested into
the application database.

It is stored in:

`open_data_fire_history`

The ingestion is performed by:

`scripts/ingest_open_data_to_mysql.py`

The expected row count is:

~~~text
628,308
~~~

The full approximately 639 MB polygon dataset is not currently ingested into
MySQL.

It should only replace or supplement the lightweight runtime representation if
a later requirement specifically needs full polygon-level runtime analysis.

### Runtime lookup

The application-facing Historical Fire lookup is implemented in:

`scripts/open_data_mysql.py`

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

Dates are returned to Backend in ISO `YYYY-MM-DD` format.

Frontend presentation formatting is outside the Data-layer contract.

### Lookup method

The MySQL-backed Historical Fire lookup:

1. receives latitude and longitude in EPSG:4326
2. constructs a geographic bounding box around the requested radius
3. uses `MBRContains` as a spatial-index prefilter
4. applies `ST_Distance_Sphere` to candidate points for the final radius test
5. counts matching historical records
6. derives the latest recorded fire season
7. derives the most recent available `start_date`
8. returns the compact contextual result

The bounding-box prefilter is important because directly applying
`ST_Distance_Sphere` across all 628,308 records requires a much larger scan.

Local validation showed the optimized query returned the same 20 km result as
the previous GeoParquet implementation for tested locations.

### Approximation and interpretation

The lightweight dataset uses a representative point for each original historical fire polygon.

Therefore:

`historical_fire_record_count`

represents the number of Historical Fire record representative points located
inside the selected search radius.

It is not exactly equivalent to counting all original fire polygons that
intersect the search area.

For example, a large historical fire polygon may intersect the search radius
even if its representative point lies outside the radius.

The full polygon dataset is retained separately when exact polygon-level
spatial analysis is required.

The lightweight result is designed for fast contextual display in the application.

It must not automatically be interpreted as the number of unique real-world
bushfire events because a fire event may be represented by more than one
spatial record.

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

## Local MySQL Setup for Data and Backend Members

The MySQL database used for local development runs through Docker Compose.

Each developer has their own local Docker MySQL database and Docker volume.

Data ingested on one team member's computer is not automatically present in
another team member's Docker database.

### 1. Create local environment configuration

From the repository root:

~~~bash
cp .env.example .env
~~~

Configure the values required by Docker and Backend.

Do not commit `.env`.

### 2. Start local MySQL

~~~bash
docker compose up -d mysql
~~~

Check that MySQL is healthy:

~~~bash
docker compose ps
~~~

### 3. Apply migration 006 to an existing database

If the developer already has an existing Docker MySQL volume created before
the spatial Open Data tables were added:

~~~bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < database/migrations/006_open_spatial_data.sql
~~~

A completely fresh Docker volume receives the current schema from:

`database/init/001_initial_schema.sql`

and therefore already includes the Open Data tables.

### 4. Ingest the processed Open Data

Run the ingestion script from the repository root:

~~~bash
DATABASE_HOST=127.0.0.1 \
python data/scripts/ingest_open_data_to_mysql.py
~~~

The script loads:

- 76 BPA records
- 9 CFA Fire District records
- 628,308 lightweight Historical Fire records

The script replaces the existing contents of the three Open Data tables during
a reload.

### 5. Verify row counts

Connect to MySQL:

~~~bash
docker compose exec mysql sh -lc \
  'exec mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"'
~~~

Then run:

~~~sql
SELECT COUNT(*) FROM open_data_bpa;
SELECT COUNT(*) FROM open_data_fire_district;
SELECT COUNT(*) FROM open_data_fire_history;
~~~

Expected:

~~~text
open_data_bpa: 76
open_data_fire_district: 9
open_data_fire_history: 628308
~~~

---

## Database Connection Locations

From the host machine:

~~~text
Host: 127.0.0.1
Port: value of MYSQL_EXPOSED_PORT
~~~

The current common local value is:

~~~text
3307
~~~

From another Docker service such as Backend:

~~~text
Host: mysql
Port: 3306
~~~

The database name and credentials are provided through:

~~~text
MYSQL_DATABASE
MYSQL_USER
MYSQL_PASSWORD
~~~

Backend uses its existing database environment configuration.

---

## Backend Handoff

The main reusable location-context entry point remains:

`data/scripts/location_context.py`

Backend consumes it through:

`backend/app/providers/data_spatial.py`

Backend imports:

~~~python
from data.scripts.location_context import get_location_context
~~~

and calls:

~~~python
result = get_location_context(
    latitude,
    longitude
)
~~~

Backend members do not need to manually implement BPA, CFA District, or
Historical Fire SQL.

`location_context.py` delegates the runtime spatial operations to:

`data/scripts/open_data_mysql.py`

The application-facing response structure remains:

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

The response includes:

- Designated Bushfire Prone Area status
- CFA Fire District
- historical bushfire context

The existing Backend adapter converts these values into the public API's
spatial provider result.

The frontend can continue consuming the same API structure.

---

## Validation

Combined response validation is implemented in:

`data/scripts/test_location_context.py`

Broader spatial fixture validation is implemented in:

`data/scripts/test_spatial_lookup.py`

The MySQL-backed lookup was also compared directly with the previous
GeoParquet-backed lookup for known test locations.

The compared values matched for:

- BPA status
- CFA Fire District
- Historical Fire record count
- latest recorded burn year
- most recent dated fire record

---

## Production

Local development uses Docker MySQL.

Production uses AWS RDS MySQL.

Ingesting the datasets into a developer's local Docker database does not
populate production RDS.

Before the production Backend uses the MySQL-backed spatial lookup, the
production database must:

1. receive migration `006_open_spatial_data.sql`
2. contain the three Open Data tables
3. receive the processed BPA, CFA Fire District, and lightweight Historical Fire data

Production credentials must not be committed to GitHub.


## Historical Fire Visualisation Data

The Data Science layer provides historical fire point records for use in the
FIREBREAK Overview visualisation.

### Purpose

The visualisation is intended to show historical fire records around the
household location so users can understand where recorded fire activity has
occurred nearby.

Historical fire records are contextual information only. They must not be
presented as a personalised bushfire risk score or prediction.

### Data source

Historical fire records are stored in:

`open_data_fire_history`

The lookup uses the same search radius as the existing Historical Fire context
(default: 20 km).

### Python function

The spatial lookup is implemented in:

`data/scripts/open_data_mysql.py`

```python
get_fire_history_points(
    cursor,
    latitude,
    longitude,
    radius_km=20,
)
```
### Returned data

Each Historical Fire point contains:

```json
{
  "latitude": -38.239540899833344,
  "longitude": 145.1447580744234,
  "season": 2025,
  "start_date": "2025-03-10"
}
```

### Runtime integration status

`get_location_context()` provides the basic spatial context used by Backend:
Bushfire Prone Area status, CFA Fire District, and the Historical Fire summary.
It does not query or return the Historical Fire point list.

`get_fire_history_points()` supplies the dedicated household-scoped Backend
endpoint:

```text
GET /api/v1/households/{household_id}/historical-fire-points
```

The query remains bounded in MySQL: the API defaults to 500 points and accepts
at most 1000. The ordinary Local Context API does not query or expose points.

### Intended visualisation

The planned Overview visualisation is a map showing:

- the household location
- Historical Fire record points within the configured 20 km radius
- the 20 km search area

The existing Historical Fire summary should remain visible:

- Records within 20 km
- Latest recorded season
- Most recent dated record

Historical Fire points provide local historical context only and must not be
labelled as a bushfire risk map or prediction.

These points are historical context only. The endpoint is not a bushfire risk
map or prediction.

## Final Runtime Architecture

- Basic Local Context uses cached-or-fresh BPA, CFA district, and Historical
  Fire summary, then obtains FDR and Weather separately.
- Preparation Support uses a fresh cached district or one narrow district SQL,
  followed by FDR and authoritative plan completion.
- Historical Fire map data uses the dedicated bounded endpoint and the existing
  20 km context.
- Static household context is cached for 24 hours by default and is invalidated
  immediately when the saved location changes.
- Direct Open Data MySQL socket timeouts are configurable with
  `APP_OPEN_DATA_DB_CONNECT_TIMEOUT_SECONDS`,
  `APP_OPEN_DATA_DB_READ_TIMEOUT_SECONDS`, and
  `APP_OPEN_DATA_DB_WRITE_TIMEOUT_SECONDS`.
- Production Backend spatial reads use MySQL/RDS only. GeoParquet remains for
  processing, ingestion, reproducibility, and comparison validation.
