# FIREBREAK — Iteration 1

FIREBREAK is a household bushfire-preparedness application. It lets a browser-owned household build and save a plan, review its completeness and local context, receive rule-based preparation guidance, and run deterministic checks against its latest saved plan.

## Architecture

```text
Vue 3 + Vite frontend
  -> HTTP JSON API (/api/v1)
  -> FastAPI routes -> Pydantic schemas -> services
  -> MySQL repositories       -> MySQL application data
  -> providers                -> Vicmap, BOM, MySQL spatial Open Data
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
- **Vicmap:** optional address suggestions and official verification/enrichment.
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
