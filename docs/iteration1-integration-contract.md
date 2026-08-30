# Iteration 1 Integration Contract

This document is the human-readable source of truth for the FIT5120 FIREBREAK
Iteration 1 application contract. It describes the current Vue, FastAPI, MySQL,
Data, and external-provider integration. FastAPI also exposes generated Swagger
documentation at `/docs` and its OpenAPI schema at `/openapi.json` while the
Backend is running.

Generated OpenAPI describes HTTP shapes. This document additionally records the
ownership rules, persistence semantics, nullable business meaning, and
Data/Database boundaries that are not clear from schemas alone.

## System boundary

| Component | Iteration 1 responsibility |
|---|---|
| Frontend | Collect and display household-plan information; call the relative `/api/v1` API; retain only the current `household_id` in local storage. |
| Backend | Validate API input, apply completion/preparation/scenario rules, coordinate providers, and expose public domain IDs. |
| MySQL | Persist application and household data using internal relational keys plus public IDs. |
| Data | Process and query BPA, CFA fire-district, and contextual fire-history datasets. |
| Official providers | Resolve addresses and supply current fire-danger and weather observations/forecasts. |

Large GIS datasets do not belong in MySQL. Completion results, immediate checks,
the basic scenario library, Fire Danger Ratings, and weather are also not stored
as dedicated application tables.

## HTTP API

All application endpoints are under `/api/v1`. JSON field names use `snake_case`.

| Method and path | Purpose | Request | Response and normal status | Important failure behavior |
|---|---|---|---|---|
| `POST /api/v1/households` | Create the application aggregate root. | Body may be omitted. Optional `display_name` is a non-empty string or `null`. | `{ "household_id": string }`, `201`. | Invalid body: `422`; database unavailable: `503`. |
| `PUT /api/v1/households/{household_id}/plan` | Validate and transactionally replace the saved plan aggregate. | `HouseholdPlan`. | Persisted `HouseholdPlan`, `200`. | Unknown household: `404`; invalid references, duplicate IDs, or cross-household IDs: `422`; database unavailable: `503`. |
| `GET /api/v1/households/{household_id}/plan` | Read the current plan. | None. | `HouseholdPlan`, `200`. | Unknown household or no saved plan: `404`; database unavailable: `503`. |
| `GET /api/v1/households/{household_id}/completion` | Calculate current section completion and immediate checks. | None. | `PlanCompletion`, `200`. | Unknown household or no saved plan: `404`; database unavailable: `503`. |
| `PUT /api/v1/households/{household_id}/location` | Resolve a Victorian address and save the latest resolved coordinates. | `{ "address": string }`. | `{ address, latitude, longitude }`, `200`. | Unknown household: `404`; unresolvable/invalid address: `422`; provider or database unavailable: `503`. |
| `GET /api/v1/households/{household_id}/local-context` | Combine saved location, spatial Data, fire danger, and weather. | None. | `LocalContext`, `200`. | Missing household/location: `404`; spatial or weather provider unavailable: `503`. Fire-danger failure is represented by `fire_danger.availability = "unavailable"`. |
| `GET /api/v1/households/{household_id}/preparation-support` | Apply the I1 rule-based plan-review timing logic. | None. | `{ status, message, sections_to_review }`, `200`. | Missing plan/location: `404`; unavailable or stale required provider data: `503`. |
| `GET /api/v1/scenarios/basic?household_id={household_id}` | List the fixed basic scenarios with household-specific relevance. | Required `household_id` query parameter. | Array of `BasicScenario`, `200`. | Missing household/plan: `404`; missing query parameter: `422`. |
| `POST /api/v1/households/{household_id}/tests` | Run one relevant basic scenario against the latest plan and persist the result. | `{ "scenario_id": string }`. | `ScenarioTestResult`, `201`. | Unknown household/plan or unsupported scenario: `404`; scenario not applicable: `422`; database unavailable: `503`. |
| `GET /api/v1/households/{household_id}/tests/{test_run_id}` | Read one persisted scenario result for the household. | None. | `ScenarioTestResult`, `200`. | Unknown household or result: `404`; database unavailable: `503`. |

FastAPI request-schema validation also returns `422`. Expected application errors
use a JSON `detail` value. Plan business validation uses:

```json
{
  "detail": {
    "message": "The household plan is invalid.",
    "errors": ["validation message"]
  }
}
```

Database errors are translated to a generic `503` response; SQL statements,
credentials, and internal database details are not part of the API contract.

### Location and context response fields

The location PUT returns the standardized `address` and resolved numeric
`latitude`/`longitude`. `LocalContext` contains:

- `location`: the same saved address and coordinates;
- `bushfire_context`: `is_bushfire_prone_area` and `fire_district`;
- `fire_danger`: a discriminated response using `availability`;
- `weather`: `temperature_c`, `relative_humidity`, `wind_speed_kmh`,
  `wind_direction`, ISO 8601 `observed_at`, and `station_name`;
- `environmental_context`: nullable `fire_history_summary`,
  `vegetation_context`, and `terrain_context`.

When fire danger is available it includes `today`, `tomorrow`, `day_3`, `day_4`,
ISO 8601 `source_updated_at`, nullable `source_url`, and `message: null`. When it
is unavailable, the rating/timestamp/source fields are `null` and `message`
explains the unavailable state. The rating vocabulary is `No Rating`, `Moderate`,
`High`, `Extreme`, and `Catastrophic`.

## Household Plan aggregate

`HouseholdPlan` is both the plan PUT body and GET response:

| Field | Type and meaning |
|---|---|
| `members` | `HouseholdMember[]`; each item has `member_id`, `display_name`, `is_dependant`, `mobility_support_required`, and nullable `support_notes`. |
| `animals` | `Animal[]`; each item has `animal_id`, `category` (`pet` or `livestock`), `animal_type`, `display_name`, and nullable `support_notes`. The contract uses `animals`, not `pets`. |
| `has_private_transport` | `boolean | null`; its three states have distinct business meanings described below. |
| `transports` | `Transport[]`; each item has `transport_id`, `transport_type` (`car`, `motorbike`, `van`, or `other`), nullable `display_name`, and `driver_member_ids`. |
| `arrangements` | Primary/backup transport IDs, nested primary/backup destinations, and a nullable meeting point. |
| `responsibilities` | `Responsibility[]`; each item has `responsibility_id`, `task_name`, and nullable primary/backup member IDs. |

A destination contains `destination_id`, `display_name`, and nullable `address`.
The arrangement fields are exactly:

- `primary_transport_id: string | null`
- `backup_transport_id: string | null`
- `primary_destination: Destination | null`
- `backup_destination: Destination | null`
- `meeting_point: string | null`

Incomplete plans may be saved. Empty collections and nullable backup fields do not
make the PUT invalid by themselves. Responsibility assignments may be `null`.
Reference IDs, when supplied, must identify entities in the same submitted plan,
IDs within each entity category must be unique, and a responsibility's backup
member must differ from its primary member. Setting `has_private_transport` to
`false` while supplying a `car`, `motorbike`, or `van` is invalid.

### Private-transport tri-state

| Value | Meaning |
|---|---|
| `null` | The household has not answered the private-transport question. |
| `true` | The household has private transport. |
| `false` | The household explicitly has no private transport. |

`null` and `false` must not be collapsed. An explicit `false` with no primary
transport satisfies the transport and backup-transport completion sections;
`null` leaves them incomplete.

## Completion and immediate checks

Completion is calculated from the latest saved plan by `PlanCompletionService`.
It is not persisted. The response contains:

- `overall_status`: `complete` or `needs_information`
- ordered `sections`: `household_profile`, `transport`, `backup_transport`,
  `primary_destination`, `backup_destination`, and `responsibilities`
- `immediate_checks`: zero or more warnings

The actual section rules require:

- at least one named member, with names/types for any animals;
- a recorded transport and primary transport, unless private transport is
  explicitly answered `false` with no primary transport;
- a backup transport under the same explicit-no-private-transport exception;
- named primary and backup destinations;
- at least one responsibility, with a task and primary member for every item.

`ImmediateCheckService` currently emits:

| Check | Condition |
|---|---|
| `missing_backup_transport` | A primary transport exists but no backup transport is set. |
| `missing_backup_destination` | A primary destination exists but no backup destination is set. |
| `missing_backup_person` | A responsibility has a primary member but no backup member. |
| `shared_transport_resource` | Primary and backup transport IDs are the same. |

These warnings are deliberately simple checks, not risk scores or predictions.

## Preparation support

Preparation support is calculated on request from plan completion plus current and
forecast Fire Danger Ratings. It returns `review_recommended` when information is
missing, ratings are at least `High`, or forecast ratings escalate; otherwise it
returns `up_to_date`. Required Fire Danger data must have an aware issue timestamp
and be no more than 24 hours old. This is plan-review support, not a bushfire
prediction or evacuation instruction.

## Basic scenarios and persisted results

The fixed I1 scenario library is Backend configuration, not a database table:

| Scenario | Enabled when | Checks |
|---|---|---|
| `vehicle_unavailable` | A primary transport ID is recorded. | Independent backup transport and valid backup driver. |
| `person_unavailable` | At least one responsibility has a primary member. | Every relevant responsibility has a valid, different backup member. |
| `destination_unavailable` | A primary destination is recorded. | Backup destination has a different ID and address. |

Every listed scenario contains `scenario_id`, `title`, `description`, `enabled`,
and nullable `disabled_reason`. Running a disabled scenario returns `422` and does
not create a completed test result.

`ScenarioTestResult` contains:

- `test_run_id`
- `scenario_id`
- `overall_status`: `pass` or `needs_attention`
- ordered `checks`, each with `check`, `status`, and `message`
- nullable `first_problem` with `section` and `message`
- `result_reason`
- UTC ISO 8601 `tested_at`

Check statuses are exactly `pass`, `fail`, and `not_checked`. A result passes only
when all emitted checks pass. Running a scenario reads but does not modify the
Household Plan. Test runs and their ordered checks are persisted in MySQL.

## Public IDs and persistence

API/domain IDs are strings. MySQL stores each public ID in `public_id` and uses an
internal `BIGINT UNSIGNED AUTO_INCREMENT` primary key for joins:

```text
API string ID -> table.public_id -> internal numeric key
internal numeric key -> table.public_id -> API string ID
```

| Table | API field |
|---|---|
| `household` | `household_id` |
| `household_member` | `member_id` |
| `animal` | `animal_id` |
| `transport` | `transport_id` |
| `destination` | `destination_id` |
| `responsibility` | `responsibility_id` |
| `test_run` | `test_run_id` |

Numeric keys are never returned to Frontend. A plan save is an aggregate
replacement inside one database transaction: members, animals, transports and
drivers, destinations, arrangements, and responsibilities either all succeed or
all roll back. Supplied public IDs are preserved across PUT/GET round trips;
internal row IDs are persistence details and may change during replacement.

### Same-household ownership

Database foreign keys guarantee referenced rows exist. They do not use triggers
or composite household keys to establish same-household ownership. Backend
validation rejects:

- a Household B member driving Household A's transport;
- Household A using Household B's transport;
- Household A using Household B's destination;
- Household A assigning a Household B member to a responsibility.

These violations produce a controlled `422`, and validation occurs before the
transaction replaces the existing plan.

## Database table responsibilities

| Table | Responsibility |
|---|---|
| `household` | Aggregate root and optional display name. |
| `household_member` | People and their dependant/mobility/support information. |
| `animal` | Pets or livestock and support information. |
| `transport` | Household transport resources. |
| `transport_driver` | Many-to-many mapping between transports and member drivers. |
| `destination` | Primary/backup destination records embedded in the API arrangement. |
| `household_arrangement` | One current tri-state transport answer and primary/backup arrangement per household. |
| `responsibility` | Preparedness tasks with nullable primary/backup member assignments. |
| `household_location` | Latest resolved address and coordinates. |
| `test_run` | Scenario result header, outcome, first problem, reason, and timestamp. |
| `test_check_result` | Ordered checks belonging to a scenario test run. |

See [`database/README.md`](../database/README.md) for setup and detailed database
rules, and [`database/init/001_initial_schema.sql`](../database/init/001_initial_schema.sql)
for the executable schema.

## Location, Data, and provider flow

```text
address
  -> VicmapAddressClient or MockAddressClient
  -> saved address/latitude/longitude
  -> DataSpatialProvider
  -> data.scripts.location_context.get_location_context(latitude, longitude)
  -> BPA + CFA fire district + fire-history context
  -> fire-danger and weather providers
  -> LocalContext response
```

`DataSpatialProvider` converts the Data layer's nested fire-history object into
the API's nullable `environmental_context.fire_history_summary`. Vegetation and
terrain fields exist in the response contract but the current provider returns
`null`; those datasets are not implemented in Iteration 1.

In live official-provider mode, runtime dependency wiring uses:

- `VicmapAddressClient` for address resolution;
- `BOMFireDangerClient` for the four-day district Fire Danger Rating;
- `BOMWeatherClient` for the nearest current weather observation.

The repository also contains a CFA RSS client/parser, but it is not the provider
selected by the current live dependency wiring. Mock providers supply stable
address, fire-danger, and weather responses for offline development and tests.
Automated tests must not depend on live network services. The spatial Data mode is
selected independently, so tests or Docker runs can use real GIS context with
mock official feeds.

## Runtime modes and configuration

| Environment variable | Values/default | Effect |
|---|---|---|
| `APP_REPOSITORY_MODE` | `mysql` (default), `memory` | Select MySQL persistence or the process-local test/development repository. |
| `APP_SPATIAL_MODE` | `data` (default), `mock` | Select the processed Data lookup or fixed spatial mock. |
| `APP_DATA_MODE` | `live` (default), `mock` | Select official address/fire-danger/weather clients or deterministic mocks. |
| `DATABASE_HOST` | `127.0.0.1` in Python; Compose supplies `mysql` | MySQL hostname. |
| `DATABASE_PORT` | `3306` | MySQL internal/connection port. |
| `MYSQL_DATABASE` | `fit5120` | Application database name. |
| `MYSQL_USER` | `fit5120_app` | Application database user. |
| `MYSQL_PASSWORD` | `change_me` example only | Application database password; real secrets must not be committed. |
| `DATABASE_POOL_SIZE` | `5` | SQLAlchemy connection-pool size. |
| `DATABASE_MAX_OVERFLOW` | `10` | Additional temporary pooled connections. |

`.env.example` contains the complete Compose development template, including
host-port overrides. Normal tests explicitly select `memory`, `mock`, and `mock`;
MySQL integration tests require a disposable `MYSQL_TEST_URL`.

## Frontend development contract

Frontend calls the relative API root `/api/v1` through `frontend/src/api/client.ts`.
During `npm run dev`, Vite proxies `/api` to `http://127.0.0.1:8000`; no browser
CORS configuration is required for that development path.

Frontend TypeScript types mirror the Pydantic response shapes. IDs remain public
strings, nullable fields must remain nullable, and timestamps are received as ISO
8601 strings. Local storage contains only `firebreak.household-id.v1` (plus
unrelated UI preferences); the saved plan and scenario results remain
Backend/MySQL data.

## Not part of Iteration 1

The current contract does not include AI-personalised scenarios or
recommendations, interactive Iteration 2 branching, reminders, sharing,
agreement checks, route planning, authentication, or production vegetation and
terrain context.
