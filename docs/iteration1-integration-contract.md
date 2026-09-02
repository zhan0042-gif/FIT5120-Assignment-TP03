# Iteration 1 Integration Contract

This is the human-readable contract for the current FIREBREAK I1 implementation. FastAPI provides generated HTTP detail at `/docs` and `/openapi.json`; this document records the application boundaries and business semantics that generated schemas do not explain.

## Boundaries and runtime

| Boundary | Responsibility |
|---|---|
| Vue frontend | Presentation, interaction, local household identifier, draft/save state, and relative API calls. |
| FastAPI routes and Pydantic schemas | HTTP boundary, structural validation, and public JSON contracts. |
| Services | Plan validation, completion, immediate checks, location/context coordination, preparation support, and scenarios. |
| Repositories / MySQL | Transactional application persistence. |
| Providers | Vicmap address lookup; BOM weather and Fire Danger data; processed spatial lookup. |
| GeoParquet | BPA, CFA Fire District, and Fire History source data—not application tables. |

Normal runtime uses MySQL, processed GeoParquet, Vicmap, and BOM. `APP_DATA_MODE=mock` selects deterministic official-provider substitutes; `APP_REPOSITORY_MODE=memory` and `APP_SPATIAL_MODE=mock` are useful controlled development/test modes. They are not the full-stack default.

## HTTP endpoints

All paths are under `/api/v1` and use snake_case JSON.

| Method and path | Current responsibility |
|---|---|
| `POST /households` | Create the browser-owned household root; returns `household_id`. |
| `GET/PUT /households/{household_id}/plan` | Read or transactionally replace the latest saved `HouseholdPlan`. |
| `GET /households/{household_id}/completion` | Derive current completion and non-blocking immediate checks. |
| `GET/PUT /households/{household_id}/location` | Read or save entered household address and optional official enrichment. |
| `GET /locations/suggestions?q=…` | Return Vicmap autocomplete candidates. A suggestion is not itself verification. |
| `GET /households/{household_id}/local-context` | Return saved location, static spatial context, current weather, and official FDR state. |
| `GET /households/{household_id}/preparation-support` | Return rule-based review guidance when FDR is usable. |
| `GET /scenarios/basic?household_id=…` | List fixed I1 scenarios relevant to the saved plan. |
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

Completion is dynamically derived from the latest saved plan, not manually ticked or stored as a completion table. It reports the six ordered sections: `household_profile`, `transport`, `backup_transport`, `primary_destination`, `backup_destination`, and `responsibilities`.

Incomplete plans remain saveable. Backup completion reflects whether an applicable usable backup exists under the current backend rules; it does not require every optional backup entry to be complete. Immediate checks are backend-owned, non-blocking practical warnings, including missing backup transport/destination/person and shared primary/backup transport resources.

## Location, context, and freshness

Saving a household address first persists its entered text and then attempts official verification. Verified coordinates allow a processed spatial lookup:

```text
verified coordinates -> GeoParquet BPA / Fire District / Fire History
                     -> derived household_location_context snapshot
                     -> current BOM weather and official FDR
```

The snapshot contains derived household-specific spatial facts, not raw datasets. It is reused for an unchanged location and invalidated when the household location is saved/changed. Dataset-version invalidation is not implemented in I1. BPA is an official designation, not a personal risk score. CFA Fire District is an operational dependency for selecting matching BOM FDR data. Fire History is contextual only; the UI may show records within 20 km, latest season, and most recent dated record.

BOM weather selects an appropriate fresh observed station; BOM weather and FDR caches are configured for about 60 minutes, but cache presence never overrides source freshness. FDR is official provider data: FIREBREAK does not calculate or fabricate it, and it may legitimately be unavailable.

## Preparation support and scenarios

Preparation Support is transparent rule-based guidance, not prediction. With usable fresh FDR, it returns `up_to_date` or `review_recommended` using FDR and saved-plan completion; it can point to incomplete sections. Unavailable or stale FDR does not generate a recommendation.

Scenarios are deterministic and run only on the latest saved plan. They do not mutate that plan. `vehicle_unavailable` requires an independent backup transport with an eligible recorded driver; `person_unavailable` requires a different valid backup person for relevant responsibilities; and `destination_unavailable` requires a genuinely different backup destination. The service evaluates available ordered backups rather than a fixed singular backup. Results are persisted independently as `test_run` and ordered `test_check_result` records.

## Frontend contract

The frontend is Vue + JavaScript. `src/api/client.js` calls relative `/api/v1`; the Vite development proxy targets `http://[::1]:8000`. `firebreak.household-id.v1` is the only application local-storage key: it is browser continuity, not authentication. A plan draft is compared with the latest persisted plan to present saved/unsaved state; failed saves stay unsaved. My Plan saves through a normal bottom-page card, not a sticky/floating bar.

See [database setup and schema](../database/README.md), [processed data](../data/README.md), and [frontend pages](../frontend/README.md).
