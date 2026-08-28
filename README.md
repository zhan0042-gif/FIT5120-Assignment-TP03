# FIT5120 Full-Stack Project

This repository contains the initial backend and infrastructure foundation for a university team project. It deliberately keeps the current architecture small and leaves other project streams to their owners.

## Project structure

- `frontend/` contains the Vue 3 + Vite + TypeScript application for Iteration 1, integrated with the FastAPI backend.
- `backend/` contains the runnable FastAPI application, its layered package structure, tests, dependencies, and Dockerfile.
- `database/` reserves locations for MySQL initialization, migrations, and future development seed data.
- `ai/` reserves a location for later AI processing and integrations; no AI architecture is selected.
- `nginx/` documents the planned reverse-proxy role for a future production deployment.
- `.github/workflows/` contains backend CI and a non-deploying manual CD scaffold.

## Technology stack

- Vue 3 + Vite + TypeScript (planned frontend)
- Python 3.12 + FastAPI (backend)
- MySQL 8
- Docker + Docker Compose
- GitHub Actions
- AWS EC2 (likely future deployment target)

## Current status

The backend provides the `/api/health` endpoint and an Iteration 1 API under
`/api/v1`. Household plans, locations, completion checks, local context,
preparation support, and basic scenario tests run end-to-end. Normal runtime
uses official Vicmap and BOM providers; set `APP_DATA_MODE=mock` explicitly for
offline provider-isolated development and tests. Persistence remains process-local,
and spatial classification remains temporary pending Database and DS integration.

The Iteration 1 endpoints are:

- `POST /api/v1/households`
- `PUT|GET /api/v1/households/{household_id}/plan`
- `GET /api/v1/households/{household_id}/completion`
- `PUT /api/v1/households/{household_id}/location`
- `GET /api/v1/households/{household_id}/local-context`
- `GET /api/v1/households/{household_id}/preparation-support`
- `GET /api/v1/scenarios/basic`
- `POST /api/v1/households/{household_id}/tests`


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

The API is exposed on `http://localhost:8000` by default. The backend uses the Compose service name `mysql` for database networking. MySQL data is stored in the named `mysql_data` volume and survives ordinary `docker compose down` and restart operations.

## Testing

After installing backend dependencies, run:

```bash
cd backend
pytest
```

The current tests are intentionally independent of MySQL. Database integration tests can introduce a disposable test database when the persistence layer exists.

## CI/CD

Backend CI runs tests and validates the FastAPI import for relevant pushes to `main` and pull requests. Frontend CI will be added after the frontend team initializes Vue and defines its scripts and tooling.

The deployment workflow is a manual, non-deploying scaffold. It does not connect to EC2 or use deployment credentials. A future deployment may authenticate to a provisioned EC2 instance, update code or container images, run `docker compose up -d --build`, and perform health checks.

## Remaining work

- Add a frontend Dockerfile and CI workflow now that the Vue app exists.
- Replace process-local persistence and temporary spatial classification when the Database and DS integrations are ready.
- Define the application database schema, migrations, and any development seed data.
- Decide and implement the AI architecture.
- Add a production Nginx configuration after routing and domains are known.
- Provision AWS EC2 and configure reviewed deployment credentials/secrets.
- Replace the manual CD scaffold with an approved production deployment process.
