# Frontend

Vue 3 + Vite + TypeScript app for Iteration 1 ("Build & Check My Preparedness").

## Scope covered

- Epic 1: Household Profile, Transport, Primary/Backup Arrangements,
  Responsibilities, and Plan Completion Overview (`/plan`).
- Epic 2: Location input, Local Bushfire/Fire-Weather Overview, and Preparation
  Timing message (`/plan`, top of page).
- Epic 3: Basic Scenario Selection, Start Test, and Basic Test Result
  (`/scenarios`).
- `/review` remains a static Iteration 3 placeholder.

## Backend integration

The complete human-readable API and ownership contract is documented in
[`docs/iteration1-integration-contract.md`](../docs/iteration1-integration-contract.md).

Epic 1 household creation, plan persistence, and completion use the FastAPI
`/api/v1` endpoints through `src/api/client.ts`. The generated household ID is
stored locally so a browser refresh can reload the authoritative plan from the
backend. Plan data itself is not stored in localStorage.

Epic 2 and Epic 3 use the FastAPI contracts. The Backend defaults to the real
processed BPA, CFA district, and fire-history Data layer plus official Vicmap and
BOM providers. Use `APP_DATA_MODE=mock` on the Backend for deterministic address,
fire-danger, and weather responses; this does not replace real spatial Data when
`APP_SPATIAL_MODE=data`.

API and domain IDs are public strings. Nullable plan fields, including the
tri-state `has_private_transport`, must be preserved. The browser stores only the
current `household_id` as application data; plans and test results remain
authoritative in Backend/MySQL.

## Development

```bash
npm install
npm run dev       # starts Vite on http://localhost:5173
npm run build     # type-checks (vue-tsc) and builds for production
```

The Vite development server proxies relative `/api` requests to FastAPI at
`http://127.0.0.1:8000`, so CORS configuration is not needed for local
development.
