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

## ID Strategy

API-exposed domain entities use two ID layers:

- an internal `BIGINT UNSIGNED AUTO_INCREMENT` primary key for database joins and foreign keys
- a stable `public_id VARCHAR(64) NOT NULL UNIQUE` supplied by Backend and returned through the API

Backend Repository code will look up a row by `public_id`, use its internal numeric key for relational operations, and map `public_id` back to the corresponding API ID when reading data.

| Table | Public ID maps to |
|---|---|
| `household` | API `household_id` |
| `household_member` | API `member_id` |
| `animal` | API `animal_id` |
| `transport` | API `transport_id` |
| `destination` | API `destination_id` |
| `responsibility` | API `responsibility_id` |
| `test_run` | API `test_run_id` |

`transport_driver`, `household_arrangement`, `household_location`, and `test_check_result` do not currently expose independent public IDs. Their numeric keys remain internal.

## Table Purpose

### household

Stores the root household record.

Main fields:

- `household_id`
- `public_id`
- `display_name`
- `created_at`
- `updated_at`

### household_member

Stores household members and support needs.

Main fields:

- `member_id`
- `public_id`
- `household_id`
- `display_name`
- `is_dependant`
- `mobility_support_required`
- `support_notes`

### animal

Stores household pets or livestock and relevant support information.

Main fields:

- `animal_id`
- `public_id`
- `household_id`
- `display_name`
- `category`
- `animal_type`
- `support_notes`

### transport

Stores household transport options.

Main fields:

- `transport_id`
- `public_id`
- `household_id`
- `transport_type`
- `display_name`

### transport_driver

Maps household members to the transport options they can drive or use.

Main fields:

- `transport_id`
- `member_id`

### destination

Stores possible evacuation destinations.

Main fields:

- `destination_id`
- `public_id`
- `household_id`
- `display_name`
- `address`
- `latitude`
- `longitude`

### household_arrangement

Stores the household's current primary and backup evacuation arrangements.

One arrangement record is stored per household.

Main fields:

- `household_id`
- `has_private_transport`
- `primary_transport_id`
- `backup_transport_id`
- `primary_destination_id`
- `backup_destination_id`
- `meeting_point`

### responsibility

Stores household preparedness tasks and the primary and backup people responsible for them.

Main fields:

- `responsibility_id`
- `public_id`
- `household_id`
- `task_name`
- `primary_member_id`
- `backup_member_id`

### household_location

Stores the household location used by the Data layer for spatial lookups.

One location record is stored per household.

Main fields:

- `household_id`
- `address`
- `suburb`
- `postcode`
- `latitude`
- `longitude`

### test_run

Stores the history of basic preparedness scenario tests.

Main fields:

- `test_run_id`
- `public_id`
- `household_id`
- `scenario_id`
- `overall_status`
- `result_reason`
- `tested_at`

### test_check_result

Stores individual check results associated with a preparedness test run.

Main fields:

- `check_result_id`
- `test_run_id`
- `check_code`
- `status`
- `message`

## Incomplete Plan Support

Household plans may be saved before every field is complete. Backend calculates completion status and immediate checks from the current saved data.

The schema therefore permits:

- a household without a display name
- a member or animal without support notes
- a transport without a display name
- a responsibility without a primary or backup member
- an arrangement without primary or backup transport or destination references

`household_arrangement.has_private_transport` has three states:

- `NULL`: the household has not answered the private-transport question
- `FALSE`: the household explicitly has no private transport
- `TRUE`: the household has private transport

The canonical Iteration 1 test statuses are:

- `test_run.overall_status`: `pass`, `needs_attention`
- `test_check_result.status`: `pass`, `fail`, `not_checked`

Technical execution failures are API/application errors rather than completed household preparedness results.

## Data Layer Boundary

Large spatial and open datasets are not stored in the MySQL application database.

The existing Data layer handles:

- Bushfire Prone Area lookup
- CFA Fire District lookup
- Fire History context

The database stores household coordinates in `household_location`.

Backend code can use those coordinates with the Data layer to resolve the location context.

Live Fire Danger Rating and weather information are also not stored as static database tables. Backend is expected to read these from official external sources.

## Backend Ownership Validation Boundary

Database foreign keys guarantee that referenced members, transports, and destinations exist. To keep the Iteration 1 relational model simple, the database does not use triggers or composite household-scoped foreign keys to prove that every referenced row belongs to the same household.

Backend Repository integration must reject cross-household references by checking that:

- each driver member belongs to the transport's household
- arrangement transports and destinations belong to the current household
- responsibility members belong to the current household

These ownership checks are mandatory before writes are committed. Persistence integration tests must cover them.

## Data That Does Not Need an Iteration 1 Table

The following information is not stored in dedicated database tables in Iteration 1:

- Plan completion status
- Immediate preparedness checks
- Basic scenario library
- CFA Fire Danger Rating
- BOM weather information

Plan completion and immediate checks can be calculated by Backend using the current plan data.

The basic scenario library can remain as Backend static configuration.

Live Fire Danger Rating and weather information should be obtained from official external feeds.

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

From other Docker services such as Backend:

```text
Host: mysql
Port: 3306
Database: value of MYSQL_DATABASE
```

From the host machine:

```text
Host: 127.0.0.1
Port: value of MYSQL_EXPOSED_PORT
Database: value of MYSQL_DATABASE
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

The MySQL image creates and selects the database configured by `MYSQL_DATABASE`. The schema script does not hardcode a separate database name.

The initial schema is automatically executed when MySQL creates a new database volume for the first time.

Initialization scripts do not automatically rerun when an existing MySQL volume is restarted.

For local development only, if the database can safely be reset:

```bash
docker compose down -v
docker compose up -d mysql
```

This deletes the local Docker database volume and recreates the database from the initialization scripts.

Do not use this reset approach for an environment containing data that must be preserved.

## Verify the Schema

To list the current tables:

```bash
docker compose exec mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE" -e "SHOW TABLES;"'
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

## Iteration 1 Verification

For a clean local database, verify:

- MySQL starts successfully
- all 11 tables are created from a clean Docker volume
- foreign key relationships are created successfully
- internal numeric primary keys and stable public IDs work together
- duplicate public IDs are rejected
- household members can store dependant and mobility support information
- animals can store category and animal type
- transport and driver relationships work
- incomplete plans can store missing display names and responsibility assignments
- `has_private_transport` preserves unanswered, false and true states
- primary and backup transport arrangements work
- primary and backup destination arrangements work
- meeting point storage works
- preparedness responsibilities work
- household location storage works
- canonical scenario test statuses can be inserted successfully
- deleting members clears responsibility assignments
- deleting a household cascades through its Iteration 1 application records

## Migrations

The directory:

```text
database/migrations/
```

is reserved for future schema migrations.

The project currently uses the initial Docker initialization schema for Iteration 1 development.
