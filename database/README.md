# Database

MySQL 8.4 is used as the application database for the FIT5120 FIREBREAK project.

The database runs locally through Docker Compose.

See [`docs/iteration1-integration-contract.md`](../docs/iteration1-integration-contract.md)
for the API/domain mapping, aggregate transaction semantics, and cross-component
ownership contract. This README remains the source for database setup and schema
details.

## Iteration 1 Schema

The initial Iteration 1 schema is defined in:

```text
database/init/001_initial_schema.sql
```

The schema currently contains 13 application tables:

- `household`
- `household_member`
- `animal`
- `transport`
- `transport_driver`
- `destination`
- `household_arrangement`
- `household_arrangement_option`
- `responsibility`
- `household_location`
- `household_location_context`
- `test_run`
- `test_check_result`

## ID Strategy

API-exposed domain entities use two ID layers:

- an internal `BIGINT UNSIGNED AUTO_INCREMENT` primary key for database joins and foreign keys
- a stable `public_id VARCHAR(64) NOT NULL UNIQUE` supplied by Backend and returned through the API

Backend Repository code looks up a row by `public_id`, uses its internal numeric key for relational operations, and maps `public_id` back to the corresponding API ID when reading data.

| Table | Public ID maps to |
|---|---|
| `household` | API `household_id` |
| `household_member` | API `member_id` |
| `animal` | API `animal_id` |
| `transport` | API `transport_id` |
| `destination` | API `destination_id` |
| `responsibility` | API `responsibility_id` |
| `test_run` | API `test_run_id` |

`transport_driver`, `household_arrangement`, `household_arrangement_option`,
`household_location`, `household_location_context`, and `test_check_result` do
not expose independent public IDs. Their numeric keys remain internal.

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
- `relationship`
- `relationship_other`

### animal

Stores household pets or livestock and relevant support information.

Main fields:

- `animal_id`
- `public_id`
- `household_id`
- `display_name`
- `category`
- `animal_type`
- `animal_type_other`
- `quantity`
- `support_notes`

### transport

Stores household transport options.

Main fields:

- `transport_id`
- `public_id`
- `household_id`
- `transport_type`
- `transport_type_other`
- `display_name`

### transport_driver

Maps household members to the transport options they can drive or use.

Main fields:

- `transport_id`
- `member_id`

### destination

Stores possible evacuation destinations. A destination name is meaningful on its
own; its detailed address is optional. Entered address text may be persisted
unverified. Officially verified entries can additionally hold canonical and
structured address fields, coordinates, and `verified_at`; unverified entries
retain entered text and have no fabricated coordinates.

Main fields:

- `destination_id`
- `public_id`
- `household_id`
- `display_name`
- `address`
- `latitude`
- `longitude`
- structured unit, street, locality, state, postcode and country columns

### household_arrangement

Stores household-level arrangement metadata such as the private-transport
answer and meeting point. One arrangement record is stored per household.

Main fields:

- `household_id`
- `has_private_transport`
- `meeting_point`

### household_arrangement_option

Stores one priority-zero primary option and zero-to-many ordered backup options.
Each option may reference transport, a destination, or both. Existing databases
upgraded through migration 004 may retain deprecated fixed primary/backup
columns on `household_arrangement`; current application code does not read or
write those compatibility columns.

Main fields:

- `arrangement_option_id`
- `household_id`
- `role`
- `priority`
- `transport_id`
- `destination_id`

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

Stores the household address. Saving it does not require official verification:
the entered full address is retained with `verification_status = unverified`
when enrichment fails. A verified row may hold canonical/structured fields and
official coordinates. Only verified coordinates can support spatial lookups.

One location record is stored per household.

Main fields:

- `household_id`
- `address`
- `suburb`
- `postcode`
- `latitude`
- `longitude`
- structured unit, street, locality, state and country columns

### household_location_context

Caches the derived BPA, CFA district, and fire-history snapshot for the current
verified household coordinates. Saving an address invalidates this snapshot.
Raw GeoParquet datasets remain in the Data layer and are not copied into MySQL.

### test_run

Stores the history of basic preparedness scenario tests.

Main fields:

- `test_run_id`
- `public_id`
- `household_id`
- `scenario_id`
- `overall_status`
- `result_reason`
- `first_problem_section`
- `first_problem_message`
- `tested_at`

### test_check_result

Stores individual check results associated with a preparedness test run.

Main fields:

- `check_result_id`
- `test_run_id`
- `check_order`
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

Backend uses verified coordinates with the Data layer to resolve local context.

Live Fire Danger Rating and weather information are also not stored as static database tables. Backend obtains them from official external providers; its
configured provider caches do not override source-freshness rules.

## Backend Ownership Validation Boundary

Database foreign keys guarantee that referenced members, transports, and destinations exist. To keep the Iteration 1 relational model simple, the database does not use triggers or composite household-scoped foreign keys to prove that every referenced row belongs to the same household.

The MySQL Backend Repository rejects cross-household references by checking that:

- each driver member belongs to the transport's household
- arrangement transports and destinations belong to the current household
- responsibility members belong to the current household

These ownership checks run before plan replacement writes are committed and are
covered by the MySQL integration tests.

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

Backend reads `DATABASE_HOST`, `DATABASE_PORT`, `MYSQL_DATABASE`, `MYSQL_USER`,
`MYSQL_PASSWORD`, `DATABASE_POOL_SIZE`, and `DATABASE_MAX_OVERFLOW`. SQLAlchemy
uses the PyMySQL driver with pooled, pre-pinged connections.

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
household_arrangement_option
household_location
household_location_context
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
- all 13 tables are created from a clean Docker volume
- foreign key relationships are created successfully
- internal numeric primary keys and stable public IDs work together
- duplicate public IDs are rejected
- household members can store dependant and mobility support information
- animals can store category and animal type
- transport and driver relationships work
- incomplete plans can store missing display names and responsibility assignments
- `has_private_transport` preserves unanswered, false and true states
- one primary and zero-to-many ordered backup arrangements work
- meeting point storage works
- preparedness responsibilities work
- household location storage works
- canonical scenario test statuses can be inserted successfully
- deleting members clears responsibility assignments
- deleting a household cascades through its Iteration 1 application records

Backend MySQL integration tests require an isolated disposable database:

```bash
cd backend
MYSQL_TEST_URL='mysql+pymysql://user:password@127.0.0.1:3306/database?charset=utf8mb4' pytest tests/test_mysql_repository.py
```

The test fixture deletes household data before and after each test. Do not use a
shared or valuable development database for this command.

## Migrations

The directory:

```text
database/migrations/
```

is reserved for future schema migrations.

Fresh database volumes receive the current schema from `init/001_initial_schema.sql`.

Existing volumes do not rerun Docker entrypoint initialization. To preserve their
data, apply each numbered upgrade script exactly once in order. For this change:

```bash
docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < database/migrations/002_i1_data_model_ux.sql

docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < database/migrations/003_location_verification_and_context_cache.sql

docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < database/migrations/004_multiple_backup_arrangements.sql

docker compose exec -T mysql sh -c \
  'mysql -u"$MYSQL_USER" -p"$MYSQL_PASSWORD" "$MYSQL_DATABASE"' \
  < database/migrations/005_destination_address_verification.sql
```

The migration adds nullable/defaulted columns, assigns existing animals a quantity
of `1`, preserves unrecognised legacy animal types in `animal_type_other`, and
backfills `suburb_or_locality` from the legacy household-location `suburb` column.
It does not delete or recreate any table or volume. The script is a numbered,
one-time upgrade; record its application per environment and do not rerun it.

The existing `address` columns remain the canonical full-address values. Structured
columns supplement them, so existing integrations and rows remain valid.

Migration 003 preserves saved household addresses even when they are not yet
officially verified. It backfills coordinate-bearing rows as verified and adds
`household_location_context`, which stores only each household's derived spatial
snapshot—not raw open datasets. I1 invalidates that snapshot when the saved
address changes; invalidation for future processed-dataset revisions is a later
enhancement.

Migration 004 normalizes arrangement options so one primary and ordered
zero-to-many backups can be stored. It migrates fixed backup values into the new
table and leaves legacy columns only for compatibility. Migration 005 adds the
same canonical and verification metadata to destination addresses that is
already used for the household location.

After applying it, verify with:

```sql
SHOW TABLES;
DESCRIBE household_member;
DESCRIBE animal;
DESCRIBE destination;
DESCRIBE household_location;
```
