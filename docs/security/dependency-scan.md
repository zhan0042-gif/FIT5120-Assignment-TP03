# Dependency Vulnerability Scan

**Purpose:** catch known-vulnerable dependencies before they reach production. This is deliverable ④ "dependency vulnerability scan evidence".

## Tools

- **Backend (Python)** — `pip-audit` — local + CI
- **Frontend (Vue / Node)** — `npm audit` — local + CI
- **Whole repo** — GitHub Dependabot (alerts + version updates) — GitHub, automated

## What actually ships

Two things reach production, and they are built by two different mechanisms. The **backend image** installs `backend/requirements.txt` and nothing else — the Dockerfile installs that file. The **frontend bundle** is built from `frontend/package-lock.json` by `npm run build` and copied to `/var/www/html/`, so every runtime dependency it pulls in ships to visitors as a built asset. A finding in either one is a production finding. The remaining requirement files matter for a different question — whether a finding is reachable in the running service.

| File | Used by | In the production image? |
| ---------------------- | -------------------------------------- | ---------------------------------------- |
| `backend/requirements.txt` | the backend container | **yes** — this is the file to scan for deploy-blocking findings |
| `backend/requirements-dev.txt` | local dev and CI (`-r requirements.txt`, then the package itself editable) | no separate packages of its own |
| `data/requirements.txt` | the DS data pipeline (geopandas, pandas, pyarrow, shapely) | **no** — the Dockerfile copies three files from `data/scripts/`, not these packages |
| `frontend/package-lock.json` | the Vue frontend, built by `npm run build` into `dist/` and copied to `/var/www/html/` | **yes** — as built assets served to the browser, not as a Python package. A runtime dependency here reaches visitors |

A finding in the data pipeline is still worth fixing, but it cannot be exploited through the deployed service, and its severity should say so rather than be reported as a production vulnerability.

## How to run (copy-paste)

**Backend** (from repo root, after installing backend deps):

```bash
pip install pip-audit
pip-audit -r backend/requirements.txt
```

**Frontend** (from the `frontend/` directory):

```bash
cd frontend
npm audit
```

Results are recorded in the vulnerability assessment report (PGP, Security folder).

**Dependabot:** enabled by the repo owner at Settings → Code security and analysis → **Dependabot alerts** and **Dependabot version updates**. It opens PRs for vulnerable packages automatically; review and merge them.

## When to run

- **On every dependency change** (new package added, or `pip install` / `npm install` output).
- **Before every deployment** — re-run both scans and record findings in the vulnerability assessment report.
- **Automatically** via Dependabot for alerts between manual runs.

## Triage rules

- **Critical / High** in a production dependency → fix before merge or deploy.
- **Medium** → resolve with the next scheduled dependency update.
- **Low / dev-only dependencies** → note, not blocking.
- **Not in the production image** → note the reduced reachability rather than reporting it as a production vulnerability (see "What actually ships").
- **Documented exception** → a Critical or High finding may be dispositioned instead of fixed, but only with a written reachability assessment (see below) and a named owner for the eventual fix. "No time to fix it" is not an exception.

## Open findings and reachability (2026-10-12)

Dependabot reports two advisories on `main`, both in `frontend/package-lock.json`. Both are dispositioned as **documented exceptions**, for two different reasons: one does not reach the browser at all, and the other reaches the browser but the affected code path is never called.

### `source-map-js` 1.2.1 — event-loop denial of service (patched in 1.2.2)

**Not in the shipped bundle.** Every package that requires it is build-time toolchain:

| Requires it | Role |
| ------------------------ | ---------------------------------------------- |
| `@vue/compiler-core` | compiles templates during `vite build` |
| `@vue/compiler-sfc` | compiles `.vue` single-file components during `vite build` |
| `postcss` | transforms CSS during `vite build` |

None of the three is imported by `frontend/src/`. Verified against a production build (`frontend/dist/`, built 2026-09-18): the markers `source-map-js`, `SourceMapConsumer`, `sourceRoot` and `originalPositionFor` appear in **no** emitted `.js` asset, while `maplibre`, `leaflet`, `pinia` and `__vue_app__` all do — so the check does detect a bundled library; it simply does not find this one. The property-style markers (`sourceRoot`, `originalPositionFor`) are the load-bearing part of the test, because minification shortens class names but not object property names.

The denial of service would have to be triggered at build time, not by a visitor. Revisit when `postcss` or the Vue compiler is next bumped.

### `maplibre-gl` 5.24.0 — sanitizer bypass in `DOM.sanitize()` (patched in 6.4.1)

**Reaches the browser, but the affected path is not called.** This one *is* in the shipped bundle, confirmed in the same build output. It is used in exactly two places:

```
frontend/src/components/fireMap/HistoricalFireMap.vue:130
frontend/src/components/scenario/TravelDisruptionMap.vue:135
    L.maplibreGL({ style: openFreeMapStyle, interactive: false }).addTo(map)
```

Both hand it to `@maplibre/maplibre-gl-leaflet` as a basemap layer only. The application never calls a maplibre `Popup`, `Marker` or any other API that feeds HTML into `DOM.sanitize()` — every popup and marker in the app belongs to Leaflet (`L.marker(...).bindPopup(...)`), a separate library with its own code path. Nothing a user or an external feed supplies reaches the maplibre sanitizer.

**Limit of this assessment:** it rests on the call sites under `frontend/src/`, not on a proof that maplibre never invokes `DOM.sanitize()` during initialisation. If a maplibre popup, marker or HTML-bearing control is ever added, this exception stops holding and the finding becomes reachable.

**Why it is not simply fixed:** the patched release is 6.4.1, so the fix is a major-version jump from 5.24.0 rather than a bump. `@maplibre/maplibre-gl-leaflet` is pinned at `^0.1.4` and its compatibility with maplibre-gl 6.x is unverified. Both call sites live in `frontend/` code owned by the frontend developer, and `frontend/**` is inside the deploy `paths:` list, so the change needs its own PR and triggers a production deploy.

## Status

- [x] Backend deps installed → first `pip-audit` run (2026-09-03) — results in the vulnerability assessment report
- [x] Frontend initialized → first `npm audit` run (2026-09-03) — 0 vulnerabilities
- [x] Dependabot alerts enabled (owner) — reporting on `main` as of 2026-09-02
- [x] **Re-checked 2026-09-14 after the dependency split** — the backend requirements are now `fastapi`, `httpx`, `PyMySQL`, `pytest`, `reportlab`, `SQLAlchemy`, `uvicorn[standard]`. The `geopandas` finding recorded in the vulnerability assessment report no longer applies to production: geopandas and pyarrow were moved out of the backend into `data/requirements.txt` on 2026-09-10, so they are not installed in the deployed image at all, and the pinned version has since moved from 1.1.1 to 1.1.2. `starlette` still arrives transitively through `fastapi` and still needs the transitive-dependency check that Dependabot does not perform
- [ ] Scan added to CI — **open**: `deploy.yml` runs `pytest` but has no `pip-audit` or `npm audit` step, so a new advisory reaches us only through Dependabot, not through the deploy itself
- [x] Dependabot findings triaged (2026-10-12) — **1 critical and 1 high** on `main`, both in `frontend/package-lock.json`: `maplibre-gl` and `source-map-js`. Both dispositioned as documented exceptions; see "Open findings and reachability" above
