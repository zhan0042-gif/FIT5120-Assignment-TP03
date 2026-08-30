# I1 Security & Privacy Requirements

**Project:** Shielding Crisis & Community Resilience (SDG 1 & 2) — I1 "Build & Check My Preparedness".
**Owner:** Cybersecurity & Deployment Lead. **Status:** draft v0.1, to be re-reviewed when the API contract freezes.

## 1. Purpose

Define what data Iteration 1 collects, how sensitive each piece is, and the handling rules for the whole team. This is the basis for the threat model and the deployment checklist.

## 2. Data classification

Iteration 1 handles household preparedness data. Combined, these fields can reveal a household's identity and home location, so even for a student prototype we follow **collect-the-minimum** and **never log or commit real data**.

- **Household display_name** — Source: Frontend form — **Low** sensitivity — prefer display_name / household role; never collect full real names if a display name suffices
- **Member support needs / mobility notes** — Source: Frontend form — **High** sensitivity — never in logs, never in public repo, never in mock/seed data
- **Pets** — Source: Frontend form — Low–Med sensitivity
- **Home location / address** — Source: Frontend form (PUT location) — **High** sensitivity — PII + geolocation; store resolved lat/lng server-side only; never in logs or error messages
- **Primary / backup destinations** — Source: Frontend form — Med–High sensitivity — reveals regular movement patterns
- **Responsibilities / household arrangements** — Source: Frontend form — Med sensitivity — who does what in a household

## 3. Minimisation principles

1. **Only collect what I1 needs.** The I1 API contract asks for display_name and household role — do not add fields like date of birth, phone numbers, or national IDs without a feature requirement.
2. **Prefer display_name / household role over real identity.** Real full names and other identifying data are out of scope for I1.
3. **No real test data in the repo.** Seed data, mock data, and examples must be obviously fake (e.g. "Alice", "123 Fake Street").
4. **No PII in logs.** The backend must not log addresses, coordinates, or support needs. Log request IDs and non-sensitive status only.

## 4. What must not appear in the repository or logs

- Real addresses or coordinates of anyone.
- Support needs / mobility notes of real people.
- Database passwords or API keys (see secret-handling).
- Any data that, combined, identifies a real household.

## 5. External data boundaries

- **Vicmap Address REST API** — data used: address → lat/lng — resolved coords are High sensitivity, keep server-side
- **CFA Fire Danger Rating feed** — data used: FDR by district — Low
- **BOM weather feed** — data used: weather context — Low
- **BPA / Fire District open data (DS layer)** — data used: spatial lookup — Low

Rule: external live data is never merged with or stored alongside household PII without a clear purpose.

## 6. Requirements for the team

- **Frontend:** escape all user-entered values before display (XSS); never bundle secrets in the build; don't send fields the contract doesn't define.
- **Backend:** validate input length/type on every endpoint; never echo raw input back into errors; external API calls need timeouts; parameterized queries / ORM only (no string-built SQL).
- **Database:** least-privilege app account (see `MYSQL_USER` in secret-handling); no passwords in repo; separate fake test data from real data.
- **DS:** respect open-data licences/attribution; processed open data must not be mixed with real household data.

## 7. Review checklist (I1)

- [ ] Fields in the frozen API contract match this classification.
- [ ] Frontend collects no fields outside the contract.
- [ ] Backend logs contain no addresses / coords / support needs.
- [ ] No real personal data in mock or seed data.
- [ ] `.env.example` has no real secrets.
