# FIREBREAK — Iteration 1

FIREBREAK is a household bushfire-preparedness application. It lets a browser-owned household build and save a plan, review its completeness and local context, receive rule-based preparation guidance, and run deterministic checks against its latest saved plan.

## Architecture

```text
Vue 3 + Vite frontend
  -> HTTP JSON API (/api/v1)
  -> FastAPI routes -> Pydantic schemas -> services
  -> MySQL repositories       -> MySQL application data
  -> providers                -> TomTom Orbis, BOM, MySQL spatial Open Data
```

The frontend handles interaction and presentation. FastAPI routes are the HTTP boundary; schemas define request/response structure; services own business rules; repositories persist application data; and providers obtain official or spatial information. Scenario and preparation-support logic is transparent, rule-based I1 logic, not AI or fire prediction.

## Application pages

| Route | Purpose |
|---|---|
| `/` | Welcome/entry page. A new browser starts a plan; a browser with a locally retained household ID can continue editing or view its overview. |
| `/plan` | Build and edit household members, animals, transport/drivers, one primary arrangement, zero-to-many ordered backups, responsibilities, meeting point, and immediate plan checks. The Save Plan section is normal page flow at the bottom. |
| `/overview` | Review derived plan completion, preparation status, household address, local bushfire context, current weather and Fire Danger information, and historical-fire context where available. |
| `/scenarios` | Run deterministic preparedness scenario tests against the latest saved plan. |

The top navigation is **My Plan | Overview | Test My Plan**. I1 has no login or account system: `firebreak.household-id.v1` is a browser-side identifier, while saved plans and results remain in the backend database.

## Data boundaries

- **MySQL:** household plans, locations, normalized arrangement options, responsibilities, and persisted scenario results.
- **MySQL spatial Open Data:** runtime BPA, CFA Fire District, and lightweight Fire History queries.
- **Processed GeoParquet:** reproducible Data processing, ingestion, and validation artifacts; not loaded by Backend runtime.
- **TomTom Orbis:** address suggestions, verification/geocoding, and reverse lookup. Live mode requires `TOMTOM_API_KEY`.
- **BOM:** current weather observations and official Fire Danger Rating data.
- **Backend-derived:** completion, non-blocking immediate checks, preparation support, scenario evaluation, and cached household-specific static spatial context.

Entered household and destination addresses can be saved without successful verification. Verified addresses may gain canonical fields and official coordinates; unverified ones retain entered text with no fabricated coordinates. A verified household location is required before spatial local context can be resolved.

See [the integration contract](docs/iteration1-integration-contract.md), [frontend documentation](frontend/README.md), [database documentation](database/README.md), and [data documentation](data/README.md) for details.

## Local development

Copy `.env.example` to `.env` and set local credentials. For the bare Windows
Backend plus Docker MySQL workflow, install the Backend and editable local Data
package once:

```powershell
docker compose up -d mysql
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements-dev.txt
$env:DATABASE_HOST = "127.0.0.1"
.\.venv\Scripts\python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The editable package makes the MySQL-backed `data.scripts.location_context`
module available when Uvicorn runs directly from `backend/`. GeoParquet tooling
has separate dependencies in `data/requirements.txt` and is not required by
normal Backend runtime. The Backend
database default is already `127.0.0.1`; the explicit local setting above makes
the host-machine topology clear and must not be used in production.

For the all-Docker development alternative, Docker starts MySQL and FastAPI:

```bash
docker compose up --build
docker compose ps
```

The API is exposed at `http://localhost:8000` and its health check is at `/api/health`. Start the frontend separately:

```bash
cd frontend
npm install
npm run dev
```

Vite serves `http://localhost:5173` and proxies `/api` to the configured FastAPI target. The default runtime uses MySQL spatial tables and live official providers. `APP_DATA_MODE=mock` supplies deterministic official-provider substitutes; tests can also select memory persistence and mock spatial data. Processing and ingestion artifacts are described in [data/README.md](data/README.md).

## Verification

```bash
cd backend
pytest

cd ../frontend
npm run build
```

MySQL integration tests require an isolated `MYSQL_TEST_URL`; tests that need it are skipped when it is absent.

## Production deployment stability

Docker Compose applies `restart: unless-stopped` to both Backend and MySQL. The
Backend waits for the MySQL healthcheck during a normal Compose start, and the
server deploy script waits for the Backend's `/api/health` check before reporting
success. The Backend runs one uvicorn process without development reload mode.

nginx is installed directly on the EC2 host rather than managed by this Compose
project. The deployment lead should verify that its host service is enabled and
healthy:

```bash
sudo systemctl is-enabled nginx
sudo systemctl status nginx --no-pager
```

On the current approximately 1 GB host, inspect memory, container state, and
recent kernel OOM events with:

```bash
free -h
docker stats --no-stream
docker ps
docker compose ps
sudo dmesg -T | grep -i -E "out of memory|killed process|oom"
sudo journalctl -k --no-pager | grep -i -E "out of memory|killed process|oom"
```

Adding approximately 1–2 GB of host swap is a deployment/host responsibility
and requires deployment-lead approval; application repository code must not
create or configure it. Swap protects against short memory spikes. Docker's
restart policy instead recovers a container after its process exits. A restart
policy does not prevent an OOM kill, so both measures address different parts
of the failure mode.


## Travel Disruption Awareness

### Overview

The Travel Disruption Awareness feature helps households check for current unplanned road disruptions near their saved evacuation destinations.

The feature uses the Victorian Department of Transport and Planning (DTP) Open Data API:

- Unplanned Disruptions – Road
- API version: v3

The feature checks for active road disruptions within a configurable radius around:

- Primary destination
- Backup destinations

The default search radius is 10 km.

> **Important:** This feature reports disruptions near a saved destination. It does not determine whether the household's actual travel route is blocked, unsafe, or inaccessible.

### User Flow

On the **Test My Plan** page, users can select:

**Check disruptions**

The application then:

1. Loads the household's saved primary and backup destinations.
2. Uses only destinations that have verified coordinates.
3. Requests current Victorian road disruption data through the backend.
4. Filters disruptions by distance from each destination.
5. Displays nearby disruption information when available, including:
   - Road name
   - Distance from destination
   - Disruption type
   - Description
   - Impact
   - Last updated time

If no verified destinations are available, the feature returns a `not_applicable` status.

If the external road disruption API is unavailable, the feature returns an unavailable state instead of causing the whole page to fail.

### Architecture

The feature follows the existing provider/service/API/frontend structure:

```text
Victorian DTP Open Data API
        ↓
VictorianRoadDisruptionClient
        ↓
TravelDisruptionService
        ↓
Household API endpoint
        ↓
Frontend API client
        ↓
Pinia store
        ↓
TravelDisruptionPanel
```

Backend endpoint:

```text
GET /api/v1/households/{household_id}/travel-disruptions
```

Optional query parameter:

```text
radius_km
```

Default radius:

```text
10 km
```

Maximum supported radius:

```text
50 km
```

### Environment Variable

The backend requires the following environment variable when running with live road disruption data:

```env
VIC_ROAD_DISRUPTIONS_API_KEY=your_key_here
```

The real API key must **not** be committed to GitHub.

For local development, store the real key in the root `.env` file.

The committed `.env.example` file should contain only a placeholder such as:

```env
VIC_ROAD_DISRUPTIONS_API_KEY=your_key_here
```

The root `.env` file is ignored by Git.

### Deployment Handover

After this feature is merged into the team repository, the teammate responsible for AWS deployment should complete the following steps.

1. Pull the latest project version containing the Travel Disruption Awareness feature.

2. Configure the following production environment variable using the team's existing secure environment or secrets management process:

```env
VIC_ROAD_DISRUPTIONS_API_KEY=<production-road-disruption-api-key>
```

3. Do not place the real API key directly in:
   - GitHub
   - `.env.example`
   - `docker-compose.yml`
   - Python source files
   - frontend source files

4. Confirm the existing production environment variables are still configured, including the existing TomTom API key:

```env
TOMTOM_API_KEY=<existing-production-key>
```

5. Rebuild and redeploy the backend so the following new backend components are included:
   - DTP road disruption provider
   - Travel disruption service
   - Household travel disruption API endpoint

6. Rebuild and redeploy the frontend so the Travel Disruption Awareness panel is included on the **Test My Plan** page.

7. Verify the backend health endpoint after deployment:

```text
GET /api/health
```

8. Create or use a household plan containing at least one verified primary or backup destination.

9. Open:

```text
Test My Plan → Travel disruption awareness
```

10. Select:

```text
Check disruptions
```

11. Confirm that the backend request:

```text
GET /api/v1/households/{household_id}/travel-disruptions?radius_km=10
```

returns HTTP `200`.

12. Confirm that the frontend correctly displays one of the supported states:
   - Nearby disruptions found
   - No disruptions found
   - Not applicable because no verified destination is available
   - Road disruption data temporarily unavailable

### Database Changes

The Travel Disruption Awareness feature does **not** introduce a new database migration.

It uses the destination coordinates already stored by the existing household planning features.

No additional database table is required specifically for this feature.

### Testing

Backend provider tests:

```bash
cd backend
pytest tests/test_road_disruption_provider.py
```

Verified result during development:

```text
8 passed
0 failed
```

Full backend test suite:

```bash
pytest
```

Verified result during development:

```text
316 passed
15 skipped
0 failed
```

The remaining warning is an existing Starlette/AnyIO deprecation warning and is not caused by this feature.

Frontend tests:

```bash
cd frontend
npm test
```

Frontend production build:

```bash
npm run build
```

Both frontend tests and the production build were verified successfully during development.

### Main Files

Backend provider:

```text
backend/app/providers/road_disruptions.py
```

Backend schema:

```text
backend/app/schemas/travel_disruptions.py
```

Backend service:

```text
backend/app/services/travel_disruptions.py
```

Backend integration changes:

```text
backend/app/api/routes/households.py
backend/app/core/config.py
backend/app/core/dependencies.py
backend/app/providers/interfaces.py
backend/app/providers/mock.py
docker-compose.yml
.env.example
```

Backend tests:

```text
backend/tests/test_road_disruption_provider.py
backend/tests/test_travel_disruption_endpoint.py
backend/tests/test_travel_disruptions.py
backend/tests/test_official_providers.py
```

Frontend:

```text
frontend/src/api/client.js
frontend/src/stores/travelDisruptions.js
frontend/src/components/scenario/TravelDisruptionPanel.vue
frontend/src/views/ScenarioTesterView.vue
```

Frontend tests:

```text
frontend/tests/travelDisruptionsStore.test.js
```

### Current Behaviour

The current version checks for road disruptions near each verified saved destination.

For example:

```text
Primary destination
        ↓
Search road disruptions within 10 km
        ↓
Display matching active disruptions

Backup destination
        ↓
Search road disruptions within 10 km
        ↓
Display matching active disruptions
```

The result is destination-based proximity information.

It should not be interpreted as confirmation that a planned route is blocked or safe.

### Current Limitations

The current implementation does not determine whether a road disruption intersects the household's actual evacuation route.

The current implementation also calculates disruption proximity from the coordinates provided by the DTP disruption geometry. This is suitable for the current destination-awareness feature but is not route-intersection analysis.

The live DTP API response structure has been validated against the current v3 endpoint during development.

### Future Improvements

Possible future improvements include:

1. **Route-aware disruption checking**

   Combine TomTom route geometry with DTP disruption geometry to determine whether a reported disruption affects the household's actual planned route.

2. **Provider caching**

   Add a short-lived backend cache for the DTP disruption dataset so that checking multiple destinations does not repeatedly download the same road disruption data.

3. **Improved disruption geometry distance calculation**

   Improve distance calculations for long LineString road disruption geometries by measuring distance to line segments rather than only using the supplied geometry points.

4. **User-selectable search radius**

   Allow users to choose a road disruption search radius instead of always using the current default of 10 km.

### Handover Status

At the time of handover:

- Backend provider tests pass.
- Full backend regression tests pass.
- Frontend tests pass.
- Frontend production build passes.
- The live Victorian DTP API has been tested successfully.
- The Travel Disruption Awareness endpoint returns HTTP `200` in local live-data testing.
- The frontend successfully displays live nearby disruption information.
- No new database migration is required for this feature.
- Production deployment still requires the deployment owner to configure `VIC_ROAD_DISRUPTIONS_API_KEY` securely in the production environment.