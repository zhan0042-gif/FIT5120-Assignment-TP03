# Security Documentation Index

Security & privacy docs for **Shielding Crisis & Community Resilience** (SDG 1 & 2). Owner: Cybersecurity & Deployment Lead.

| Document | What it covers | Read by |
| ---------------------- | ------------------------------------------------------- | ----------------------- |
| `secret-handling.md` | Rules for API keys, DB passwords and environment variables, plus who owns each production key and how to rotate it | Everyone, before the first push |
| `privacy-requirements.md` | What data the app collects, its sensitivity, the minimisation rules, and every external boundary | All developers, DS |
| `threat-model.md` | Attack surface and risk register for the deployed architecture, including the CI/CD path | The team, before deploy |
| `dependency-scan.md` | How dependency vulnerabilities are scanned and triaged | The security lead |
| `deployment-checklist.md` | Pre-deployment security checklist, signed off before release | The security lead, at deploy |

Related: `docs/infrastructure/deployment-plan.md` — the deployed architecture and the CI/CD path that updates it.

**Status:** I1–I2 — security docs current as of 2026-09-14. Deployment live since 2026-09-02; deploy pipeline hardened 2026-09-13; dependency scan run 2026-09-03 (results in the vulnerability assessment report); deployment checklist in progress (two items open: T12 input bounds, Dependabot triage).

## Repository layout

- `docs/security/` — all security docs (test/scan evidence is submitted in PGP, not stored in the repo)
