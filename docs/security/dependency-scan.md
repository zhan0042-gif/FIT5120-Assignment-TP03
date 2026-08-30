# Dependency Vulnerability Scan

**Purpose:** catch known-vulnerable dependencies before they reach production. This is deliverable ④ "dependency vulnerability scan evidence".

## Tools

| Stack | Tool | Where it runs |
|---|---|---|
| Backend (Python) | `pip-audit` | local + CI |
| Frontend (Vue / Node) | `npm audit` | local + CI |
| Whole repo | GitHub Dependabot (alerts + version updates) | GitHub, automated |

## How to run (copy-paste)

**Backend** (from repo root, after installing backend deps):

```bash
pip install pip-audit
pip-audit -r backend/requirements.txt
```

Save the output as evidence:

```bash
pip-audit -r backend/requirements.txt > docs/security/evidence/$(date +%F)_pip-audit.txt
```

**Frontend** (once the frontend team initializes the Vue app):

```bash
cd frontend
npm audit
npm audit --json > ../docs/security/evidence/$(date +%F)_npm-audit.json
```

**Dependabot:** enabled by the repo owner at Settings → Code security and analysis → **Dependabot alerts** and **Dependabot version updates**. It opens PRs for vulnerable packages automatically; review and merge them.

## When to run

- **On every dependency change** (new package added, or `pip install` / `npm install` output).
- **Before every deployment** — re-run both scans and archive the output.
- **Automatically** via Dependabot for alerts between manual runs.

## Triage rules

- **Critical / High** in a production dependency → fix before merge or deploy.
- **Medium** → resolve with the next scheduled dependency update.
- **Low / dev-only dependencies** → note, not blocking.

## Status

- [ ] Backend deps installed → first `pip-audit` run, archive to `evidence/`
- [ ] Frontend initialized → first `npm audit` run, archive to `evidence/`
- [ ] Dependabot alerts enabled (owner)
- [ ] Scan added to CI (recommended after both stacks exist)
