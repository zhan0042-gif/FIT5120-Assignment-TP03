# Security Documentation Index

Security & privacy docs for **Shielding Crisis & Community Resilience** (SDG 1 & 2). Owner: Cybersecurity & Deployment Lead.

- **secret-handling** — rules for API keys, DB passwords, env vars. **Everyone before first push.** (for all developers)
- **privacy-requirements** — what data I1 collects, sensitivity, minimisation rules. (for all developers, DS)
- **threat-model** — attack surface + risk list for the I1 architecture. (for the team, before deploy)
- `dependency-scan.md` — how dependency vulnerabilities are scanned and triaged. (for the security lead)
- `deployment-checklist.md` — pre-deployment security checklist — signed off before release. (for the security lead, deploy)

**Status:** I1 — security docs drafted; deployment live since 2026-09-02; dependency scan run 2026-09-03 (results in the vulnerability assessment report); deployment checklist in progress.

## Repository layout

- `docs/security/` — all security docs (test/scan evidence is submitted in PGP, not stored in the repo)
