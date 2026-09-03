# Dependency Vulnerability Scan

**Purpose:** catch known-vulnerable dependencies before they reach production. This is deliverable ④ "dependency vulnerability scan evidence".

## Tools

- **Backend (Python)** — `pip-audit` — local + CI
- **Frontend (Vue / Node)** — `npm audit` — local + CI
- **Whole repo** — GitHub Dependabot (alerts + version updates) — GitHub, automated

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

Results are recorded in the Iteration 1 vulnerability assessment report (PGP, Security folder).

**Dependabot:** enabled by the repo owner at Settings → Code security and analysis → **Dependabot alerts** and **Dependabot version updates**. It opens PRs for vulnerable packages automatically; review and merge them.

## When to run

- **On every dependency change** (new package added, or `pip install` / `npm install` output).
- **Before every deployment** — re-run both scans and record findings in the vulnerability assessment report.
- **Automatically** via Dependabot for alerts between manual runs.

## Triage rules

- **Critical / High** in a production dependency → fix before merge or deploy.
- **Medium** → resolve with the next scheduled dependency update.
- **Low / dev-only dependencies** → note, not blocking.

## Status

- [x] Backend deps installed → first `pip-audit` run (2026-09-03) — results in the vulnerability assessment report
- [x] Frontend initialized → first `npm audit` run (2026-09-03) — 0 vulnerabilities
- [x] Dependabot alerts enabled (owner) — reporting on `main` as of 2026-09-02
- [ ] Scan added to CI (recommended after both stacks exist)
