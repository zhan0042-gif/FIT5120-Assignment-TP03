# Frontend

Vue 3 + Vite **JavaScript** frontend for FIREBREAK Iteration 1.

## Pages and navigation

The top navigation is **My Plan | Overview | Test My Plan**.

| Route | Responsibility |
|---|---|
| `/` | Welcome page. New browsers start a preparedness plan; browsers with a local household ID can continue editing or open Overview. |
| `/plan` | Plan editing: people, animals, transport/eligible drivers, primary arrangement, zero-to-many backup arrangements, responsibilities, meeting point, and immediate checks. |
| `/overview` | Saved-plan completion, rule-based preparation status, household address, local spatial context, weather, official Fire Danger information, and historical-fire context. |
| `/scenarios` | Deterministic tests of the latest saved plan. |

There is no I1 authentication system. The browser stores only the current household identifier under `firebreak.household-id.v1`; plans, locations, and test results are server-side data.

## Plan save behaviour

The page edits a detached plan draft. A saved plan loads as saved; edits make the draft unsaved; a successful save restores saved state; and a failed save leaves the draft unsaved for retry. The Save Plan card is in normal page flow at the end of My Plan, not sticky or floating. Incomplete plans remain saveable: completion and immediate checks are server-derived advice.

`arrangements` uses one primary choice plus `backup_arrangements[]`. A backup may have transport, a destination, or both. Destination names are distinct from optional addresses; the shared autocomplete component may enrich a selected official address, but manual address text remains saveable when unverified.

## Backend integration

`src/api/client.js` calls the relative `/api/v1` API and centralizes JSON/error handling. Pinia stores retain UI state and request status; persisted plan data remains authoritative in FastAPI/MySQL. The full endpoint and business contract is in [the integration contract](../docs/iteration1-integration-contract.md).

During `npm run dev`, Vite proxies `/api` to `http://[::1]:8000`. This is local development configuration, not a production deployment requirement.

## Development

```bash
npm install
npm run dev
npm run build
```
