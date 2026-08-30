# Iteration 1 Database ERD

This ERD represents the Iteration 1 application database for the FIT5120 FIREBREAK project.

```mermaid
erDiagram

    HOUSEHOLD {
        BIGINT household_id PK
        VARCHAR display_name
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    HOUSEHOLD_MEMBER {
        BIGINT member_id PK
        BIGINT household_id FK
        VARCHAR display_name
        BOOLEAN is_dependant
        BOOLEAN mobility_support_required
        TEXT support_notes
        TIMESTAMP created_at
    }

    ANIMAL {
        BIGINT animal_id PK
        BIGINT household_id FK
        VARCHAR display_name
        VARCHAR category
        VARCHAR animal_type
        TEXT support_notes
        TIMESTAMP created_at
    }

    TRANSPORT {
        BIGINT transport_id PK
        BIGINT household_id FK
        VARCHAR transport_type
        VARCHAR display_name
        TEXT notes
        TIMESTAMP created_at
    }

    TRANSPORT_DRIVER {
        BIGINT transport_id PK, FK
        BIGINT member_id PK, FK
    }

    DESTINATION {
        BIGINT destination_id PK
        BIGINT household_id FK
        VARCHAR display_name
        VARCHAR address
        DECIMAL latitude
        DECIMAL longitude
        TEXT notes
        TIMESTAMP created_at
    }

    HOUSEHOLD_ARRANGEMENT {
        BIGINT household_id PK, FK
        BIGINT primary_transport_id FK
        BIGINT backup_transport_id FK
        BIGINT primary_destination_id FK
        BIGINT backup_destination_id FK
        VARCHAR meeting_point
        TEXT notes
        TIMESTAMP created_at
        TIMESTAMP updated_at
    }

    RESPONSIBILITY {
        BIGINT responsibility_id PK
        BIGINT household_id FK
        VARCHAR task_name
        BIGINT primary_member_id FK
        BIGINT backup_member_id FK
        TEXT notes
        TIMESTAMP created_at
    }

    HOUSEHOLD_LOCATION {
        BIGINT household_id PK, FK
        VARCHAR address
        VARCHAR suburb
        VARCHAR postcode
        DECIMAL latitude
        DECIMAL longitude
        TIMESTAMP updated_at
    }

    TEST_RUN {
        BIGINT test_run_id PK
        BIGINT household_id FK
        VARCHAR scenario_id
        ENUM overall_status
        TEXT result_reason
        TIMESTAMP tested_at
    }

    TEST_CHECK_RESULT {
        BIGINT check_result_id PK
        BIGINT test_run_id FK
        VARCHAR check_code
        ENUM status
        TEXT message
    }


    HOUSEHOLD ||--o{ HOUSEHOLD_MEMBER : has
    HOUSEHOLD ||--o{ ANIMAL : has
    HOUSEHOLD ||--o{ TRANSPORT : has
    HOUSEHOLD ||--o{ DESTINATION : has
    HOUSEHOLD ||--o| HOUSEHOLD_ARRANGEMENT : has
    HOUSEHOLD ||--o{ RESPONSIBILITY : defines
    HOUSEHOLD ||--o| HOUSEHOLD_LOCATION : has
    HOUSEHOLD ||--o{ TEST_RUN : performs

    TRANSPORT ||--o{ TRANSPORT_DRIVER : assigned_to
    HOUSEHOLD_MEMBER ||--o{ TRANSPORT_DRIVER : can_drive

    TRANSPORT o|--o{ HOUSEHOLD_ARRANGEMENT : primary_transport
    TRANSPORT o|--o{ HOUSEHOLD_ARRANGEMENT : backup_transport

    DESTINATION o|--o{ HOUSEHOLD_ARRANGEMENT : primary_destination
    DESTINATION o|--o{ HOUSEHOLD_ARRANGEMENT : backup_destination

    HOUSEHOLD_MEMBER ||--o{ RESPONSIBILITY : primary_person
    HOUSEHOLD_MEMBER o|--o{ RESPONSIBILITY : backup_person

    TEST_RUN ||--o{ TEST_CHECK_RESULT : contains
```

## Relationship Summary

### Household relationships

A household can have:

- many household members
- many animals
- many transport options
- many destinations
- one current household arrangement
- many responsibilities
- one household location
- many preparedness test runs

### Transport and drivers

`transport_driver` is a junction table between:

- `transport`
- `household_member`

This supports a many-to-many relationship because:

- one transport option may have multiple possible drivers
- one household member may be able to drive multiple transport options

### Household arrangements

Each household can have one current `household_arrangement`.

The arrangement may reference:

- one primary transport option
- one backup transport option
- one primary destination
- one backup destination
- one meeting point

The transport and destination references are optional because a household may not have completed every part of its preparedness plan yet.

### Responsibilities

Each responsibility belongs to one household.

A responsibility has:

- one primary household member
- an optional backup household member

Examples include:

- drive the household
- collect pets
- prepare medication
- contact family members

### Household location

Each household can have one current household location.

The latitude and longitude are used by the Data layer to obtain:

- Bushfire Prone Area status
- CFA Fire District
- local Fire History context

Large spatial datasets are not stored in the application database.

### Preparedness testing

A household can have multiple `test_run` records over time.

Each test run can contain multiple `test_check_result` records.

This allows the system to keep a history of preparedness tests and the individual checks that contributed to each test result.

## Iteration Boundary

This ERD contains only the application tables required for Iteration 1.

The following are intentionally not represented as database tables in Iteration 1:

- plan completion status
- immediate preparedness checks
- basic scenario library
- CFA Fire Danger Rating
- BOM weather data
- BPA polygons
- CFA Fire District polygons
- Fire History spatial datasets
- vegetation datasets
- terrain datasets

Plan completion and immediate checks can be calculated by Backend.

The basic scenario library can remain as Backend static configuration.

Live Fire Danger Rating and weather information are obtained from official external sources.

Spatial bushfire context remains in the Data layer.