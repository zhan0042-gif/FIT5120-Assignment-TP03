# FIT5120 Full-Stack Project

This repository contains the Iteration 1 full-stack implementation for the
FIT5120 FIREBREAK university team project. The current architecture remains
deliberately small and keeps future project streams outside the I1 contract.

## Project structure

- `frontend/` contains the Vue 3 + Vite + TypeScript application for Iteration 1, integrated with the FastAPI backend.
- `backend/` contains the runnable FastAPI application, its layered package structure, tests, dependencies, and Dockerfile.
- `database/` contains the Iteration 1 MySQL application schema and reserves locations for migrations and future development seed data.
- `ai/` reserves a location for later AI processing and integrations; no AI architecture is selected.
- `nginx/` documents the planned reverse-proxy role for a future production deployment.
- `.github/workflows/` contains backend CI and a non-deploying manual CD scaffold.

## Technology stack

- Vue 3 + Vite + TypeScript
- Python 3.12 + FastAPI (backend)
- MySQL 8
- Docker + Docker Compose
- GitHub Actions
- AWS EC2 (likely future deployment target)

## Current status

The Iteration 1 Vue frontend, FastAPI API, MySQL application persistence, and
processed spatial Data layer are integrated. Household plans, locations,
completion checks, local context, preparation support, and basic scenario tests
run end-to-end under `/api/v1`.

See [`docs/iteration1-integration-contract.md`](docs/iteration1-integration-contract.md)
for the human-readable API, business-rule, persistence, ownership, and provider
contract.

The application runtime always uses MySQL, processed BPA/CFA district/fire-history
datasets, and official Vicmap/BOM providers; no mock runtime mode is available.

The Iteration 1 endpoints are:

- `POST /api/v1/households`
- `PUT|GET /api/v1/households/{household_id}/plan`
- `GET /api/v1/households/{household_id}/completion`
- `PUT /api/v1/households/{household_id}/location`
- `GET /api/v1/households/{household_id}/local-context`
- `GET /api/v1/households/{household_id}/preparation-support`
- `GET /api/v1/scenarios/basic?household_id={household_id}`
- `POST /api/v1/households/{household_id}/tests`
- `GET /api/v1/households/{household_id}/tests/{test_run_id}`


## Local backend setup

Python 3.12 is recommended. From the repository root:

```bash
python -m venv backend/.venv
```

Activate the environment, then install dependencies and start the API:

```bash
pip install -r backend/requirements.txt
uvicorn app.main:app --reload --app-dir backend
```

Open `http://localhost:8000/api/health` to verify the service.

## Docker setup

Copy `.env.example` to `.env` and replace the example development passwords before sharing or deploying the environment. Then use:

```bash
docker compose up --build
docker compose ps
docker compose down
```

The API is exposed on `http://localhost:8000` by default. The backend uses the
Compose service name `mysql` for database networking. MySQL data is stored in the
named `mysql_data` volume and survives ordinary `docker compose down` and restart
operations.

## Testing

After installing backend dependencies, run:

```bash
cd backend
pytest
```

Most tests use the in-memory repository. MySQL integration tests run when
`MYSQL_TEST_URL` points to a disposable database initialized with
`database/init/001_initial_schema.sql`; they are skipped otherwise. Never point
these cleanup-based tests at a database containing data that must be retained.

## CI/CD

Backend CI runs tests and validates the FastAPI import for relevant pushes to
`main` and pull requests. The initialized Frontend currently has no dedicated CI
workflow; its available verification command is `npm run build`.

The deployment workflow is a manual, non-deploying scaffold. It does not connect to EC2 or use deployment credentials. A future deployment may authenticate to a provisioned EC2 instance, update code or container images, run `docker compose up -d --build`, and perform health checks.

## Remaining work
- Add migrations before evolving the initial schema beyond Iteration 1.
- Decide and implement the AI architecture.
- Add a production Nginx configuration after routing and domains are known.
- Provision AWS EC2 and configure reviewed deployment credentials/secrets.
- Replace the manual CD scaffold with an approved production deployment process.
