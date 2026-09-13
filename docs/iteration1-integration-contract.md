# Iteration 1 Integration Contract

This is the human-readable contract for the current FIREBREAK I1 implementation. FastAPI provides generated HTTP detail at `/docs` and `/openapi.json`; this document records the application boundaries and business semantics that generated schemas do not explain.

## Boundaries and runtime

| Boundary | Responsibility |
|---|---|
| Vue frontend | Presentation, interaction, local household identifier, draft/save state, and relative API calls. |
| FastAPI routes and Pydantic schemas | HTTP boundary, structural validation, and public JSON contracts. |
| Services | Plan validation, completion, immediate checks, location/context coordination, preparation support, and scenarios. |
| Repositories / MySQL | Transactional application persistence. |
| Providers | TomTom Orbis address lookup; BOM weather and Fire Danger data; MySQL-backed spatial lookup. |
| GeoParquet | BPA, CFA Fire District, and Fire History source data—not application tables. |

Normal runtime uses MySQL spatial tables, TomTom Orbis, and BOM. GeoParquet is retained for processing, ingestion, and validation, but is not loaded by Backend runtime. `APP_DATA_MODE=mock` selects deterministic official-provider substitutes; `APP_REPOSITORY_MODE=memory` and `APP_SPATIAL_MODE=mock` are useful controlled development/test modes. They are not the full-stack default.

## HTTP endpoints

All paths are under `/api/v1` and use snake_case JSON.

| Method and path | Current responsibility |
|---|---|
| `POST /households` | Create the browser-owned household root; returns `household_id`. |
| `GET/PUT /households/{household_id}/plan` | Read or transactionally replace the latest saved `HouseholdPlan`. |
| `GET /households/{household_id}/completion` | Derive current completion and non-blocking immediate checks. |
| `GET/PUT /households/{household_id}/location` | Read or save entered household address and optional official enrichment. |
| `PUT /households/{household_id}/location/device` | Save latitude/longitude explicitly shared through the browser's one-shot current-location action. No postal address is inferred or verified. |
| `GET /locations/suggestions?q=…` | Return up to eight TomTom Orbis Suggest v3 candidates, filtered to Victoria. A suggestion is not itself verification and may omit coordinates. |
| `POST /locations/nearby-addresses` | Return nearby TomTom Orbis Reverse Geocode v2 candidates for coordinates. Candidates remain unverified until the user explicitly confirms one through the normal address-save flow. |
| `GET /households/{household_id}/local-context` | Return saved location, static spatial context, current weather, and official FDR state. |
| `GET /households/{household_id}/historical-fire-points?limit=500` | Return a bounded 20 km Historical Fire point set. Limit must be 1-1000; the response reports total/returned counts and truncation. |
| `GET /households/{household_id}/preparation-support` | Return rule-based review guidance when FDR is usable. |
| `GET /scenarios/basic?household_id=…` | List fixed I1 scenarios relevant to the saved plan. |
| `POST /households/{household_id}/rendezvous-simulation` | Estimate when every member reaches the primary destination from their declared usual location. Requires a 100% complete plan. Not stored: figures reflect traffic at call time. |
| `POST /households/{household_id}/tests` | Run one deterministic scenario and persist its result. |
| `GET /households/{household_id}/tests/{test_run_id}` | Retrieve that stored result. |

Unknown resources return `404`; schema/business validation returns `422`; unavailable persistence/providers use controlled availability errors. Fire Danger has an explicit in-response unavailable state rather than a fabricated rating.

## Saved plan contract

`HouseholdPlan` has `members`, `animals`, nullable tri-state `has_private_transport`, `transports`, `arrangements`, and `responsibilities`. It intentionally accepts an incomplete but structurally valid plan.

```json
{
  "arrangements": {
    "primary_transport_id": "transport_1",
    "primary_destination": { "destination_id": "destination_1", "display_name": "Relative's house" },
    "backup_arrangements": [
      { "transport_id": "transport_2", "destination": { "destination_id": "destination_2", "display_name": "Community centre" } }
    ],
    "meeting_point": null
  }
}
```

There is one primary arrangement and zero-to-many ordered backup arrangements. Each backup may carry transport, destination, or both. IDs in this contract are public strings, never MySQL numeric keys. The backend validates duplicate IDs and same-household references before aggregate replacement.

Destinations have a meaningful `display_name` and an optional `address`. Both household and destination address payloads can include canonical/structured fields, coordinates, `verification_status`, and `verified_at`; `selected_address` is accepted as a UI selection hint and is not persisted in the response. Persistence is distinct from verification: manual entered address text is retained as `unverified` when official verification cannot enrich it, and no coordinates are invented.

## Completion and immediate checks

Completion is dynamically derived from the latest saved plan, not manually ticked or stored as a completion table. It reports the seven ordered sections: `household_profile`, `member_locations`, `transport`, `backup_transport`, `primary_destination`, `backup_destination`, and `responsibilities`.

`member_locations` is complete when every household member has a declared usual location. It was added on 2026-09-10 for the rendezvous simulation: plans saved before that change report 86% until a location is added to each member. No data is lost and no existing endpoint breaks, but the change is visible to users.

Incomplete plans remain saveable. Backup completion reflects whether an applicable usable backup exists under the current backend rules; it does not require every optional backup entry to be complete. Immediate checks are backend-owned, non-blocking practical warnings, including missing backup transport/destination/person and shared primary/backup transport resources.

## Location, context, and freshness

Saving a household address first persists its entered text and then attempts official verification. A complete address is checked with TomTom Orbis Geocode v2; verification requires a unique Victorian result with valid coordinates and a compatible normalized house number and street. For a selected suggestion, locality and postcode are supporting disambiguation signals rather than unconditional equality gates; free text remains more conservative. A unit/apartment value is preserved when its base street address verifies, with an explicit message that the unit itself was not independently verified. Ambiguous, incomplete, contradictory, or missing matches remain saved but unverified without invented coordinates. Autocomplete makes one bounded TomTom Orbis Suggest v3 request with a four-second upstream deadline; the browser also cancels superseded requests and applies a six-second client deadline.

The alternative current-location action runs only after an explicit click and uses one `navigator.geolocation.getCurrentPosition` request (never continuous watching). Its coordinates are persisted with `location_source: "device_location"`, an empty address, and `verification_status: "unverified"`. These trusted, explicitly shared coordinates can drive Local Context while the UI clearly states that no postal address was verified. Both verified address coordinates and device coordinates allow a processed spatial lookup:

After coordinates are saved, the Backend may query TomTom Orbis for nearby
address candidates (the provider currently normally returns one result). Reverse lookup failure does not affect coordinate
persistence or Local Context. A candidate is displayed for confirmation and is
only saved and verified through the existing address workflow after the user
chooses **Use this address**; unit candidates are never selected silently.

```text
verified address coordinates --+
                               +-> MySQL BPA / Fire District / Fire History
device-shared coordinates -----+-> derived household_location_context snapshot
                                   -> current BOM weather and official FDR
```

The snapshot contains derived household-specific spatial facts, not raw datasets. It is reused for an unchanged location for at most 24 hours by default and invalidated immediately when the household location is saved/changed. Dataset-version invalidation is not implemented in I1. BPA is an official designation, not a personal risk score. CFA Fire District is an operational dependency for selecting matching BOM FDR data. Fire History is contextual only; the summary and dedicated bounded map endpoint use a 20 km radius and must not be presented as prediction.

BOM weather selects an appropriate fresh observed station; BOM weather and FDR caches are configured for about 60 minutes, but cache presence never overrides source freshness. Controlled weather unavailability produces `weather: null` while retaining spatial context and FDR. FDR is official provider data: FIREBREAK does not calculate or fabricate it, and it may legitimately be unavailable.

## Preparation support and scenarios

Preparation Support is transparent rule-based guidance, not prediction. With usable fresh FDR, it returns `up_to_date` or `review_recommended` using FDR and saved-plan completion; it can point to incomplete sections. Unavailable or stale FDR does not generate a recommendation.

Scenarios are deterministic and run only on the latest saved plan. They do not mutate that plan. `vehicle_unavailable` requires an independent backup transport with an eligible recorded driver; `person_unavailable` requires a different valid backup person for relevant responsibilities; and `destination_unavailable` requires a genuinely different backup destination. The service evaluates available ordered backups rather than a fixed singular backup. Results are persisted independently as `test_run` and ordered `test_check_result` records.

## Frontend contract

The frontend is Vue + JavaScript. `src/api/client.js` calls relative `/api/v1`; the Vite development proxy targets `http://[::1]:8000`. `firebreak.household-id.v1` is the only application local-storage key: it is browser continuity, not authentication. A plan draft is compared with the latest persisted plan to present saved/unsaved state; failed saves stay unsaved. My Plan saves through a normal bottom-page card, not a sticky/floating bar.

See [database setup and schema](../database/README.md), [processed data](../data/README.md), and [frontend pages](../frontend/README.md).

### Rendezvous simulation

`POST /households/{household_id}/rendezvous-simulation` answers "how long until
everyone is together?" using TomTom Matrix Routing, in one request for the whole
household. Nothing is stored, and no figure is ever estimated locally: a
fabricated travel time is worse than none.

It always returns `200` unless the household is unknown (`404`). `status` is one
of:

- `ready` — `member_etas`, `everyone_together_seconds`, `slowest_member_id`, `warnings`
- `not_applicable` — `unavailable_reason`, plus `missing_sections` when the plan is incomplete
- `unavailable` — the routing provider failed or timed out; no figures are returned

The middle two are answers rather than errors, matching how `BasicScenario` uses
`enabled` and `disabled_reason`.

Warnings are deterministic rules over saved plan data, not AI output: members
flagged `is_dependant` or `mobility_support_required` cannot travel alone,
members absent from every `driver_member_ids` cannot drive to a car-based
estimate, and the slowest member is named with the wait they impose.
