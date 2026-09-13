<!--
Each item below maps to something that has already broken production once.
Please tick it, or delete the line if it does not apply.
-->

## What this PR changes

<!-- One or two sentences. Link the issue or the iteration goal. -->

## Before merging

- [ ] **This PR changes the database schema.**
      Migration file(s) required: `<!-- e.g. database/migrations/008_member_usual_location.sql -->`
      I have already applied them to the production RDS database, before merging this PR.
      <!-- scripts/deploy.sh deploys code only: it never runs migrations. If code
           that reads a new column reaches production before the column exists,
           the feature breaks in production and nothing warns you at merge time.
           Delete this line if the PR does not touch the schema. -->

- [ ] **This PR adds or changes an environment variable.**
      I have added the name to `.env.example` and set the real value in the
      server's `.env` (`/home/ubuntu/FIT5120-Assignment-TP03/.env`, which is
      deliberately not in git).
      <!-- The backend reads configuration at container start, so a missing
           required value can stop the whole backend from starting and take the
           entire site down, rather than failing one feature.
           Delete this line if no env var changed. -->

- [ ] **I know that merging this triggers a production deploy.**
      Changes under `backend/`, `frontend/`, `data/`, `scripts/`,
      `docker-compose.yml`, or `.github/workflows/deploy.yml` are picked up by
      the deploy workflow and go live on cubesix.me automatically.
