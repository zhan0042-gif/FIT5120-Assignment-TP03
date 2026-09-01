# Security Documentation Index

Security & privacy docs for **Shielding Crisis & Community Resilience** (SDG 1 & 2). Owner: Cybersecurity & Deployment Lead.

- **secret-handling** — rules for API keys, DB passwords, env vars. **Everyone before first push.** (for all developers)
- **privacy-requirements** — what data I1 collects, sensitivity, minimisation rules. (for all developers, DS)
- **threat-model** — attack surface + risk list for the I1 architecture. (for the team, before deploy)
- `dependency-scan.md` *(pending)* — how dependency vulnerabilities are scanned; results archived in `evidence/`. (for the security lead)
- `deployment-checklist.md` *(pending)* — pre-deployment security checklist — signed off before release. (for the security lead, deploy)

**Status:** I1 — 3 core docs drafted; dependency scanning and deployment checklist pending (blocked on system maturity).

## Repository layout

- `docs/security/` — all security docs
- `docs/security/evidence/` — scan reports and test evidence (see its README)
