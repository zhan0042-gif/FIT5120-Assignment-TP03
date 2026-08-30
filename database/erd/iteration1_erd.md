# Iteration 1 Database ERD

This ERD represents the Iteration 1 application database for the FIT5120 FIREBREAK project.

> Notes:
> - This version is simplified for readability.
> - It shows table names, key fields, and relationship types.
> - Data types are intentionally omitted.
> - `transport_driver` is the junction table between `household_member` and `transport`.

```mermaid
%%{init: {"flowchart": {"curve": "linear"}} }%%
flowchart LR

    HH["<b>HOUSEHOLD</b><br/>PK household_id<br/>display_name<br/>created_at<br/>updated_at"]

    HM["<b>HOUSEHOLD_MEMBER</b><br/>PK member_id<br/>FK household_id<br/>display_name<br/>is_dependant<br/>mobility_support_required<br/>support_notes<br/>created_at"]

    AN["<b>ANIMAL</b><br/>PK animal_id<br/>FK household_id<br/>display_name<br/>category<br/>animal_type<br/>support_notes<br/>created_at"]

    TR["<b>TRANSPORT</b><br/>PK transport_id<br/>FK household_id<br/>transport_type<br/>display_name<br/>notes<br/>created_at"]

    DE["<b>DESTINATION</b><br/>PK destination_id<br/>FK household_id<br/>display_name<br/>address<br/>latitude<br/>longitude<br/>notes<br/>created_at"]

    HA["<b>HOUSEHOLD_ARRANGEMENT</b><br/>PK, FK household_id<br/>FK primary_transport_id<br/>FK backup_transport_id<br/>FK primary_destination_id<br/>FK backup_destination_id<br/>meeting_point<br/>notes<br/>created_at<br/>updated_at"]

    HL["<b>HOUSEHOLD_LOCATION</b><br/>PK, FK household_id<br/>address<br/>suburb<br/>postcode<br/>latitude<br/>longitude<br/>updated_at"]

    RS["<b>RESPONSIBILITY</b><br/>PK responsibility_id<br/>FK household_id<br/>task_name<br/>FK primary_member_id<br/>FK backup_member_id<br/>notes<br/>created_at"]

    TD["<b>TRANSPORT_DRIVER</b><br/>PK, FK transport_id<br/>PK, FK member_id"]

    TRUN["<b>TEST_RUN</b><br/>PK test_run_id<br/>FK household_id<br/>scenario_id<br/>overall_status<br/>result_reason<br/>tested_at"]

    TCR["<b>TEST_CHECK_RESULT</b><br/>PK check_result_id<br/>FK test_run_id<br/>check_code<br/>status<br/>message"]

    HH -->|"1 to many"| HM
    HH -->|"1 to many"| AN
    HH -->|"1 to many"| TR
    HH -->|"1 to many"| DE
    HH -->|"1 to 1"| HA
    HH -->|"1 to 1"| HL
    HH -->|"1 to many"| RS
    HH -->|"1 to many"| TRUN

    HM -->|"1 to many"| TD
    TR -->|"1 to many"| TD

    HM -->|"1 to many as primary member"| RS
    HM -->|"0 or many as backup member"| RS

    TR -->|"0 or many as primary / backup transport"| HA
    DE -->|"0 or many as primary / backup destination"| HA

    TRUN -->|"1 to many"| TCR
```

## Relationship Summary

- `household` to `household_member`: **one-to-many**
- `household` to `animal`: **one-to-many**
- `household` to `transport`: **one-to-many**
- `household` to `destination`: **one-to-many**
- `household` to `household_arrangement`: **one-to-one**
- `household` to `household_location`: **one-to-one**
- `household` to `responsibility`: **one-to-many**
- `household` to `test_run`: **one-to-many**
- `household_member` to `transport`: **many-to-many via `transport_driver`**
- `test_run` to `test_check_result`: **one-to-many**
- `responsibility.primary_member_id` references one `household_member`
- `responsibility.backup_member_id` optionally references one `household_member`
- `household_arrangement` optionally references:
  - one primary transport
  - one backup transport
  - one primary destination
  - one backup destination