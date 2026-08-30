# Database

MySQL 8.4 is used as the application database for the FIT5120 FIREBREAK project.

The database runs locally through Docker Compose.

## Iteration 1 Schema

The initial Iteration 1 schema is defined in:

```text
database/init/001_initial_schema.sql
```

The schema currently contains 11 application tables:

- `household`
- `household_member`
- `animal`
- `transport`
- `transport_driver`
- `destination`
- `household_arrangement`
- `responsibility`
- `household_location`
- `test_run`
- `test_check_result`

## Table Purpose

### household

Stores the main household record.

### household_member

Stores household members and support needs.

### animal

Stores household animals or pets and relevant support notes.

### transport

Stores household transport options.

### transport_driver

Maps household members to transport they are able to drive.

### destination

Stores possible evacuation destinations.

### household_arrangement

Stores primary and backup transport or destination arrangements.

### responsibility

Stores household preparedness responsibilities, including primary and backup people.

### household_location

Stores the household coordinates used by the Data layer for spatial lookups.

### test_run

Stores the result of a basic preparedness scenario test.

### test_check_result

Stores individual checks associated with a scenario test run.

## Data Layer Boundary

Large spatial and open datasets are not stored in the MySQL application database.

The existing Data layer handles:

- Bushfire Prone Area lookup
- CFA Fire District lookup
- Fire History context

The application database only stores household coordinates in `household_location`.

Backend code can use those coordinates with the Data layer to resolve location context.

Live Fire Danger Rating and weather information are also not stored as static database tables. These are expected to come from official external sources through the Backend.

## Local Setup

Create a local environment file from the example:

```bash
cp .env.example .env
```

The project Docker MySQL instance can use a different exposed host port if another local MySQL server is already using port `3306`.

For example:

```text
MYSQL_EXPOSED_PORT=3307
```

Start MySQL:

```bash
docker compose up -d mysql
```

Check its status:

```bash
docker compose ps
```

The MySQL service should show:

```text
healthy
```

## Database Connection

From other Docker services such as the Backend:

```text
Host: mysql
Port: 3306
Database: fit5120
```

From the host machine:

```text
Host: 127.0.0.1
Port: value of MYSQL_EXPOSED_PORT
Database: fit5120
```

Use the credentials configured in the local `.env` file.

Do not commit `.env` or real deployment credentials.

## Initialisation

Files inside:

```text
database/init/
```

are mounted into:

```text
/docker-entrypoint-initdb.d
```

by Docker Compose.

The initial schema is automatically executed when MySQL creates a new database volume for the first time.

Important: initialization scripts do not automatically rerun when an existing MySQL volume is restarted.

For local development only, if the database can safely be reset:

```bash
docker compose down -v
docker compose up -d mysql
```

This deletes the local Docker database volume and recreates the database from the initialization scripts.

Do not use this reset approach for environments containing data that must be preserved.

## Verify the Schema

To list the current tables:

```bash
docker compose exec mysql mysql \
  -u fit5120_app \
  -pchange_me \
  fit5120 \
  -e "SHOW TABLES;"
```

Expected Iteration 1 tables:

```text
animal
destination
household
household_arrangement
household_location
household_member
responsibility
test_check_result
test_run
transport
transport_driver
```

## Migrations

The directory:

```text
database/migrations/
```

is reserved for future schema migrations.

The project currently uses the initial Docker initialization schema for Iteration 1 development.