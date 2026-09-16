# Historical Fire Map – Area Burned Handover

## Feature Summary

This feature adds **burned-area information** to the Historical Fire Map.

Each historical bushfire marker popup now displays:

- Recorded date
- Approximate location
- Area burned
- Distance from the household location

Example:

```text
Historical fire

Recorded
15 Apr 2025

Approximate location
12 Example Road, Victoria

Area burned
125.75 ha

Distance from your home
15.3 km
```

The burned area is **not calculated by the application**.

It comes directly from the existing historical bushfire source dataset using the source field:

```text
AREA_HA
```

During preprocessing, this field is renamed to:

```text
area_ha
```

The application only stores, returns, and displays this value.

---

## Data Flow

The complete data flow is:

```text
FIRE_HISTORY.shp
        ↓
process_fire_history.py
        ↓
fire_history.parquet
        ↓
create_fire_history_lightweight.py
        ↓
fire_history_lightweight.parquet
        ↓
ingest_open_data_to_mysql.py
        ↓
open_data_fire_history MySQL table
        ↓
open_data_mysql.py
        ↓
FastAPI historical-fire endpoint
        ↓
Frontend Fire Map
        ↓
Historical fire popup
```

The lightweight historical fire dataset uses a representative point for each fire rather than storing the full fire polygon.

Therefore:

```text
Map marker = approximate representative fire location
Area burned = original historical fire record area
```

The map marker does not represent the complete burned boundary.

The `area_ha` value is still taken from the original source record.

---

## Files Changed

The feature modifies the following files:

```text
backend/app/schemas/households.py
backend/tests/test_historical_fire_map.py
data/processed/fire_history_lightweight.parquet
data/scripts/create_fire_history_lightweight.py
data/scripts/ingest_open_data_to_mysql.py
data/scripts/open_data_mysql.py
database/migrations/009_add_fire_history_area_ha.sql
frontend/src/components/fireMap/HistoricalFireMap.vue
```

---

## 1. Lightweight Historical Fire Dataset

File:

```text
data/scripts/create_fire_history_lightweight.py
```

Previously, the lightweight historical fire dataset retained:

```text
season
start_date
geometry
```

It now retains:

```text
season
start_date
area_ha
geometry
```

The `area_ha` field comes from the full processed historical fire dataset.

The lightweight historical fire dataset was regenerated successfully.

Current record count:

```text
628,308 historical bushfire records
```

Current missing `area_ha` count:

```text
0
```

The generated file is:

```text
data/processed/fire_history_lightweight.parquet
```

The file size increased because the additional `area_ha` column is now retained.

---

## 2. Database Migration

A new migration was added:

```text
database/migrations/009_add_fire_history_area_ha.sql
```

Migration content:

```sql
-- FIREBREAK
-- Add historical fire burned area to the lightweight runtime table.

ALTER TABLE open_data_fire_history
ADD COLUMN area_ha DECIMAL(18,6) NULL AFTER start_date;
```

The final database type must be:

```sql
DECIMAL(18,6)
```

Do **not** change it back to:

```sql
DECIMAL(12,6)
```

An initial local test used `DECIMAL(12,6)`, but the ingestion failed because the historical dataset contains fire-area values above 1,000,000 hectares.

One observed maximum value was approximately:

```text
2,383,892 hectares
```

Therefore:

```sql
DECIMAL(18,6)
```

is required.

---

## 3. Historical Fire Data Ingestion

File:

```text
data/scripts/ingest_open_data_to_mysql.py
```

The historical fire ingestion now inserts:

```text
season
start_date
area_ha
geometry
```

The `area_ha` value is converted to a Python float before insertion.

The local ingestion was successfully tested.

Result:

```text
Inserted Historical Fire rows: 628308/628308
Open spatial data ingestion completed successfully.
```

After ingestion, the local database was verified with:

```text
total_rows = 628308
missing_area_rows = 0
```

---

## 4. Runtime Historical Fire Queries

File:

```text
data/scripts/open_data_mysql.py
```

The following functions now select and return `area_ha`:

```python
get_fire_history_points(...)
```

and:

```python
get_nearest_fire_history_point(...)
```

Each historical fire point can now contain:

```json
{
  "latitude": -37.70,
  "longitude": 145.20,
  "season": 2025,
  "start_date": "2025-02-03",
  "area_ha": 125.75,
  "distance_km": 5.4
}
```

The `area_ha` value is therefore available in:

```text
points
most_recent_fire
nearest_fire
```

---

## 5. Backend Schema

File:

```text
backend/app/schemas/households.py
```

The `HistoricalFirePoint` model now contains:

```python
area_ha: float | None = Field(
    default=None,
    ge=0,
    allow_inf_nan=False,
)
```

`NearestHistoricalFirePoint` inherits from `HistoricalFirePoint`.

Therefore the nearest historical fire automatically supports `area_ha` as well.

The same `HistoricalFirePoint` model is also used for:

```text
points
most_recent_fire
```

so those responses also include `area_ha`.

---

## 6. Frontend Fire Map

File:

```text
frontend/src/components/fireMap/HistoricalFireMap.vue
```

The historical fire popup now displays:

```text
Area burned
```

Example:

```text
Area burned
0.15 ha
```

Large values are formatted with thousands separators and up to two decimal places.

Example:

```text
Area burned
2,383,892.12 ha
```

If an area value is unavailable, the frontend displays:

```text
Area unavailable
```

The popup now contains:

```text
Historical fire

Recorded
...

Approximate location
...

Area burned
...

Distance from your home
...
```

---

## 7. Backend Test Changes

File:

```text
backend/tests/test_historical_fire_map.py
```

The historical fire test data now includes `area_ha`.

The tests verify `area_ha` for:

```text
points
most_recent_fire
nearest_fire
```

Focused backend test command:

```bash
cd backend
pytest tests/test_historical_fire_map.py
```

Result:

```text
9 passed
```

One Starlette/AnyIO deprecation warning may appear.

That warning is unrelated to this feature.

---

## 8. Frontend Tests

Frontend test command:

```bash
cd frontend
npm test
```

Result:

```text
45 passed
0 failed
```

---

## 9. Frontend Production Build

Command:

```bash
npm run build
```

Result:

```text
Build successful
```

A Vite chunk-size warning may appear because the Fire Map bundle is relatively large.

This does not prevent the production build from succeeding.

---

## 10. MapLibre Local Dependency Note

During local testing, the first production build failed because `maplibre-gl` was declared in `package.json` but was not installed in the local `node_modules`.

The project already contains:

```text
maplibre-gl
```

in:

```text
frontend/package.json
```

Running:

```bash
npm install
```

installed the missing local dependency.

After that:

```bash
npm run build
```

completed successfully.

No `package.json` or `package-lock.json` changes were required for this feature.

---

## 11. Local Browser Verification

The feature was successfully tested locally in the browser.

A historical fire marker popup displayed:

```text
Area burned
0.15 ha
```

The popup layout remained correct.

The following information was visible together:

```text
Historical fire
Recorded
Approximate location
Area burned
Distance from your home
```

The feature therefore works through the complete local flow:

```text
Historical fire source data
→ lightweight parquet
→ MySQL
→ backend query
→ FastAPI response
→ frontend Fire Map popup
```

---

## 12. Overview / Household Plan Summary Regression Check

The existing Overview page and the recently merged Household Plan Summary were also checked locally.

This feature did **not** modify the Overview page.

It did **not** modify:

```text
Household Plan Summary
Household members
Member daytime locations
Key locations
Primary destination
Backup destination
Meeting point
Responsibilities
Plan completion
Preparation status
Household address
PDF export
```

The local Overview page matched the existing main-site Overview behaviour.

The Household Plan Summary remained intact.

The Area Burned feature is isolated to the historical fire data pipeline, API schema, tests, and Fire Map popup.

---

## 13. Local Docker Note

During local browser testing, the backend initially failed to start with:

```text
VIC_ROAD_DISRUPTIONS_API_KEY is required when APP_DATA_MODE=live.
```

The local `.env` already contained the DTP API key.

However, `docker-compose.yml` was not passing the variable into the backend container.

For local testing, this line was temporarily added under the backend environment section:

```yaml
VIC_ROAD_DISRUPTIONS_API_KEY: ${VIC_ROAD_DISRUPTIONS_API_KEY}
```

After this change:

```bash
docker compose up --build
```

started successfully.

The backend reported:

```text
Application startup complete.
Uvicorn running on http://0.0.0.0:8000
GET /api/health 200 OK
```

The temporary Docker Compose modification was then restored and was **not included in the Area Burned feature commit**.

Do not hard-code the actual API key in the repository.

---

## 14. Git Information

Feature branch:

```text
feature/fire-map-area-burned
```

Feature commit:

```text
643079e feat: add burned area to historical fire map
```

After the commit:

```text
nothing to commit, working tree clean
```

The commit contains exactly these eight feature files:

```text
backend/app/schemas/households.py
backend/tests/test_historical_fire_map.py
data/processed/fire_history_lightweight.parquet
data/scripts/create_fire_history_lightweight.py
data/scripts/ingest_open_data_to_mysql.py
data/scripts/open_data_mysql.py
database/migrations/009_add_fire_history_area_ha.sql
frontend/src/components/fireMap/HistoricalFireMap.vue
```

The temporary Docker Compose modification is not part of the commit.

---

# Remaining Handover Work

Development of the Area Burned feature is complete.

The remaining workflow is mainly deployment:

```text
Push feature branch
→ Create pull request
→ Review
→ Merge into main
→ Apply production database migration
→ Re-ingest production historical fire data
→ Deploy backend
→ Verify API
→ Deploy frontend
→ Verify Fire Map
→ Perform regression smoke test
```

---

## Step 1 – Push the Feature Branch

From the project root:

```bash
git push -u origin feature/fire-map-area-burned
```

---

## Step 2 – Create the Pull Request

Suggested PR title:

```text
Add burned area information to historical fire map
```

Suggested PR description:

```markdown
## Summary

Adds burned-area information to historical bushfire records displayed on the Fire Map.

## Changes

- retain `area_ha` in the lightweight historical fire dataset
- regenerate the lightweight fire-history parquet
- add `area_ha` to the runtime MySQL table
- ingest burned-area values into MySQL
- return `area_ha` from historical fire database queries
- expose `area_ha` through the FastAPI historical-fire schema
- display Area burned in historical fire marker popups
- update backend tests

## Testing

- backend historical-fire tests: 9 passed
- frontend tests: 45 passed
- frontend production build: successful
- local browser verification: successful

## Important deployment note

After merging, production must:

1. apply `database/migrations/009_add_fire_history_area_ha.sql`
2. re-ingest historical fire data so existing rows receive `area_ha`
3. deploy backend and frontend
4. verify Area burned appears in production Fire Map popups
```

---

## Step 3 – Review and Merge

After the pull request is approved, merge:

```text
feature/fire-map-area-burned
```

into:

```text
main
```

Confirm that the merged branch contains:

```text
database/migrations/009_add_fire_history_area_ha.sql
```

and:

```text
data/processed/fire_history_lightweight.parquet
```

---

# Production Deployment

## Step 4 – Apply the Production Database Migration

Before the updated backend is used against production data, apply:

```text
database/migrations/009_add_fire_history_area_ha.sql
```

The migration is:

```sql
ALTER TABLE open_data_fire_history
ADD COLUMN area_ha DECIMAL(18,6) NULL AFTER start_date;
```

After applying it, verify the table:

```sql
DESCRIBE open_data_fire_history;
```

Expected column:

```text
area_ha decimal(18,6)
```

Do not use:

```text
decimal(12,6)
```

because that type cannot store the largest historical fire values.

---

## Step 5 – Re-ingest Production Historical Fire Data

This step is required.

Applying the migration only creates the new column.

Existing production historical fire rows will otherwise have:

```text
area_ha = NULL
```

The historical fire data must therefore be re-ingested.

Use the production ingestion workflow based on:

```text
data/scripts/ingest_open_data_to_mysql.py
```

If running directly in the appropriate production environment:

```bash
python data/scripts/ingest_open_data_to_mysql.py
```

The expected number of historical fire records for the current dataset is approximately:

```text
628,308
```

---

## Step 6 – Verify Production Database Data

After ingestion, run:

```sql
SELECT
    COUNT(*) AS total_rows,
    SUM(area_ha IS NULL) AS missing_area_rows
FROM open_data_fire_history;
```

Expected for the current dataset:

```text
total_rows ≈ 628308
missing_area_rows = 0
```

Optional verification:

```sql
SELECT
    fire_history_id,
    season,
    start_date,
    area_ha
FROM open_data_fire_history
WHERE area_ha IS NOT NULL
LIMIT 10;
```

Confirm that `area_ha` contains valid numeric values.

---

## Step 7 – Deploy the Backend

Deploy the backend version containing the updated:

```text
data/scripts/open_data_mysql.py
backend/app/schemas/households.py
```

The historical fire endpoint should now expose:

```json
{
  "area_ha": 125.75
}
```

for historical fire records when the value is available.

---

## Step 8 – Verify the Production API

Use a household with a verified location.

Call:

```text
GET /api/v1/households/{household_id}/historical-fire-points
```

Verify that returned historical fire points contain:

```json
{
  "latitude": -37.70,
  "longitude": 145.20,
  "season": 2025,
  "start_date": "2025-02-03",
  "area_ha": 125.75,
  "distance_km": 5.4
}
```

Also verify:

```text
most_recent_fire.area_ha
```

and:

```text
nearest_fire.area_ha
```

when those records are present.

If the API returns:

```json
"area_ha": null
```

for all records, check whether the historical fire data was re-ingested after the migration.

---

## Step 9 – Deploy the Frontend

Deploy the frontend containing the updated:

```text
frontend/src/components/fireMap/HistoricalFireMap.vue
```

No Overview or Household Plan Summary changes are required for this feature.

---

## Step 10 – Production Fire Map Smoke Test

Open the production website.

Navigate to:

```text
Fire Map
```

Click several historical fire markers.

Verify each popup displays:

```text
Historical fire

Recorded
...

Approximate location
...

Area burned
... ha

Distance from your home
... km
```

Check a small value such as:

```text
0.15 ha
```

and, if available nearby, a larger value to confirm number formatting.

Large values should appear similar to:

```text
2,383,892.12 ha
```

---

## Step 11 – Production Regression Check

Verify the following existing functionality after deployment:

```text
My Plan
Overview
Household Plan Summary
Fire Map
Test My Plan
PDF export
Household address
Member locations
Primary destination
Backup destination
Responsibilities
Nearest historical fire card
Most recent historical fire card
Bushfire context
Weather information
Fire danger information
```

Pay particular attention to the Overview page.

Confirm the existing merged Household Plan Summary remains unchanged.

The Area Burned feature should not affect that functionality.

---

# Troubleshooting

## Problem: Fire Map Shows "Area unavailable"

If the popup displays:

```text
Area unavailable
```

first inspect the historical-fire API response.

If it contains:

```json
"area_ha": null
```

check the database:

```sql
SELECT
    COUNT(*) AS total_rows,
    SUM(area_ha IS NULL) AS missing_area_rows
FROM open_data_fire_history;
```

If the area values are missing, the production historical fire data probably has not been re-ingested since adding the column.

Run the historical fire ingestion again.

---

## Problem: MySQL Reports "Out of range value for column 'area_ha'"

Check the database type.

Incorrect:

```sql
DECIMAL(12,6)
```

Correct:

```sql
DECIMAL(18,6)
```

If necessary:

```sql
ALTER TABLE open_data_fire_history
MODIFY COLUMN area_ha DECIMAL(18,6) NULL;
```

The committed migration already contains the correct type.

---

## Problem: Local Docker Backend Fails With DTP API Key Error

Possible error:

```text
VIC_ROAD_DISRUPTIONS_API_KEY is required when APP_DATA_MODE=live.
```

This issue is unrelated to the Area Burned feature.

Check whether the root `.env` contains:

```text
VIC_ROAD_DISRUPTIONS_API_KEY
```

without printing the actual secret.

If the key exists but Docker does not receive it, the local backend environment may require:

```yaml
VIC_ROAD_DISRUPTIONS_API_KEY: ${VIC_ROAD_DISRUPTIONS_API_KEY}
```

Do not commit an actual API key.

---

## Problem: Frontend Build Cannot Find MapLibre

Possible error:

```text
Rolldown failed to resolve import "maplibre-gl/dist/maplibre-gl.css"
```

Check:

```bash
npm list maplibre-gl
```

If it shows:

```text
(empty)
```

run:

```bash
npm install
```

Then verify:

```bash
npm list maplibre-gl
```

and rerun:

```bash
npm run build
```

The MapLibre dependency is already declared in the project package configuration.

---

# Completed Validation

Backend focused tests:

```text
PASS
9 passed
```

Frontend tests:

```text
PASS
45 passed
0 failed
```

Frontend production build:

```text
PASS
```

Historical fire MySQL ingestion:

```text
PASS
628308 / 628308 records
```

Local historical fire area completeness:

```text
PASS
0 missing area values
```

Local browser Fire Map verification:

```text
PASS
```

Local popup confirmed:

```text
Area burned
0.15 ha
```

Overview / Household Plan Summary regression check:

```text
PASS
```

---

# Final Status

Feature development status:

```text
COMPLETE
```

Current branch:

```text
feature/fire-map-area-burned
```

Current feature commit:

```text
643079e feat: add burned area to historical fire map
```

Remaining actions:

```text
1. Push feature branch
2. Create pull request
3. Review and merge into main
4. Apply production database migration
5. Re-ingest production historical fire data
6. Verify production database area values
7. Deploy backend
8. Verify historical-fire API
9. Deploy frontend
10. Verify Area burned in production Fire Map popup
11. Run regression smoke test
```

Once those steps are complete, the Historical Fire Map Area Burned enhancement is fully deployed.