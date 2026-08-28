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

Epic 1 household creation, plan persistence, and completion use the FastAPI
`/api/v1` endpoints through `src/api/client.ts`. The generated household ID is
stored locally so a browser refresh can reload the authoritative plan from the
backend. Plan data itself is not stored in localStorage.

Epic 2 and Epic 3 remain on temporary deterministic mocks until their
integration patches. The mock address is stored in localStorage. To demonstrate
the current Epic 2 mock states:

- An address containing `VIC` returns a full local-context result.
- An address without `VIC` demonstrates the unavailable-data state.
- An address containing `error` demonstrates an API-error state.

## Development

```bash
npm install
npm run dev       # starts Vite on http://localhost:5173
npm run build     # type-checks (vue-tsc) and builds for production
```

The Vite development server proxies relative `/api` requests to FastAPI at
`http://127.0.0.1:8000`, so CORS configuration is not needed for local
development.
