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

**Status:** I1–I3 — security docs current as of 2026-10-07. Deployment live since 2026-09-02; deploy pipeline hardened 2026-09-13; I1 and I2 archived at `/i1/` and `/i2/` on 2026-10-06; dependency scan run 2026-09-03 and penetration test 2026-10-05 (results in the vulnerability assessment report and pen test report); deployment checklist in progress.

**Open security items:** T12 input bounds (`backup_arrangements` and `Destination.address`), Dependabot triage, `follow_redirects=False` on the two keyed clients (T6), and the provider-retention question for the user-authored text the Safety Insights question box transmits (T22). The archive-path 401 probe (T21) was run against production on 2026-10-07 — `/`, `/i1/` and `/i2/` each return `401` — and is closed.

**Boundary added 2026-10-07:** the Safety Insights question box sends a **user-authored** question to the NVIDIA hosted model, which is a different shape from the household-derived summary T13 already covered. It is recorded as T22 in the threat model, with its payload, controls and residual in `privacy-requirements.md` §5. The model returns reviewed-answer **ids only**; no text it writes is ever shown to a user or stored.

**Correction recorded 2026-10-06:** the threat model and the Security Plan both stated that evacuation destination coordinates were transmitted to the Victorian road disruption feed, and rated it High. The provider sends no household-derived field at all — the request carries pagination and the key only, and coordinates are used locally for radius filtering. T18 is corrected and the severity lowered; the privacy boundary is documented in `privacy-requirements.md` §5.

## Repository layout

- `docs/security/` — all security docs (test/scan evidence is submitted in PGP, not stored in the repo)
