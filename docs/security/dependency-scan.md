# Dependency Vulnerability Scan

**Purpose:** catch known-vulnerable dependencies before they reach production. This is deliverable ④ "dependency vulnerability scan evidence".

## Tools

- **Backend (Python)** — `pip-audit` — local + CI
- **Frontend (Vue / Node)** — `npm audit` — local + CI
- **Whole repo** — GitHub Dependabot (alerts + version updates) — GitHub, automated

## What actually ships

Only `backend/requirements.txt` reaches production: the Dockerfile installs that file and nothing else. The other two files matter for a different question — whether a finding is reachable in the running service.

| File | Used by | In the production image? |
| ---------------------- | -------------------------------------- | ---------------------------------------- |
| `backend/requirements.txt` | the backend container | **yes** — this is the file to scan for deploy-blocking findings |
| `backend/requirements-dev.txt` | local dev and CI (`-r requirements.txt`, then the package itself editable) | no separate packages of its own |
| `data/requirements.txt` | the DS data pipeline (geopandas, pandas, pyarrow, shapely) | **no** — the Dockerfile copies three files from `data/scripts/`, not these packages |

A finding in the data pipeline is still worth fixing, but it cannot be exploited through the deployed service, and its severity should say so rather than be reported as a production vulnerability.

## How to run (copy-paste)

**Backend** (from repo root, after installing backend deps):

```bash
pip install pip-audit
pip-audit -r backend/requirements.txt
```

**Frontend** (once the frontend team initializes the Vue app):

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

## Status

- [x] Backend deps installed → first `pip-audit` run (2026-09-03) — results in the vulnerability assessment report
- [x] Frontend initialized → first `npm audit` run (2026-09-03) — 0 vulnerabilities
- [x] Dependabot alerts enabled (owner) — reporting on `main` as of 2026-09-02
- [x] **Re-checked 2026-09-14 after the dependency split** — the backend requirements are now `fastapi`, `httpx`, `PyMySQL`, `pytest`, `reportlab`, `SQLAlchemy`, `uvicorn[standard]`. The `geopandas` finding recorded in the vulnerability assessment report no longer applies to production: geopandas and pyarrow were moved out of the backend into `data/requirements.txt` on 2026-09-10, so they are not installed in the deployed image at all, and the pinned version has since moved from 1.1.1 to 1.1.2. `starlette` still arrives transitively through `fastapi` and still needs the transitive-dependency check that Dependabot does not perform
- [ ] Scan added to CI (recommended after both stacks exist)
- [ ] Dependabot findings triaged (1 high + 1 moderate reported on `main` as of 2026-09-02)
