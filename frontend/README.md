# Frontend

Vue 3 + Vite + TypeScript app for Iteration 1 ("Build & Check My Preparedness"). Built against a
mock backend (see `src/api/mockBackend.ts`) so it does not wait on the real Database/Backend/DS
work — see the project root `README.md` for overall project status.

## Scope covered (Iteration 1)

- **Epic 1** — Household Profile, Transport, Primary/Backup Arrangements, Responsibilities, Plan
  Completion Overview (`/plan`).
- **Epic 2** — Location input, Local Bushfire/Fire-Weather Overview, Preparation Timing message
  (`/plan`, top of page).
- **Epic 3** — Basic Scenario Selection, Start Test, Basic Test Result (`/scenarios`).
- Loading, empty, validation-error, API-error and data-unavailable states on every page.
- `/review` (Review & reminders) is a static placeholder — that functionality is Iteration 3
  (Epic 7/8) and depends on Backend endpoints that don't exist yet.

## Mock data / swapping to the real Backend

`src/api/client.ts` is a thin wrapper whose functions map 1:1 to the documented I1 API contract
(`POST/GET/PUT /api/v1/households/...`). Every component and Pinia store imports from
`client.ts`, never from `mockBackend.ts` directly. When the real Backend exists, only
`client.ts` needs to change to call `fetch`/`axios` instead of the mock — component code and
data shapes (`src/types/*.ts`) should not need to change.

The mock backend persists the household plan and address to `localStorage` so state survives a
page reload. To demo specific states via the address field on `/plan`:

- An address containing `VIC` returns a full local-context result.
- An address without `VIC` demonstrates the "data unavailable" state (AC4, US2.1).
- An address containing `error` demonstrates the API-error state with retry.

## Development

```bash
npm install
npm run dev       # starts Vite on http://localhost:5173
npm run build      # type-checks (vue-tsc) and builds for production
```
