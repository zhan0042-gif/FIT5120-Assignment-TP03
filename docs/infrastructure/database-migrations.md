# Production database migrations

Production schema migrations numbered `009` and later are applied automatically
by the disposable Compose `migration` service. Migrations `001` through `008`
are the legacy baseline: they were managed manually and are never replayed by
the automatic runner.

Before automatic migrations are first enabled in production, operators must
confirm that production RDS already matches the legacy `001` through `008`
baseline. The runner cannot detect a legacy migration that was missed during a
manual deployment. After this check, migrations `009` and later are managed
automatically.

Before a new Backend container is activated, `scripts/deploy.sh`:

1. builds the migration image;
2. validates that the dedicated migration credentials are configured;
3. applies pending files in `database/migrations/` in filename order;
4. runs eligible one-time jobs in `database/data_migrations/`; and
5. starts Backend only after both migration commands succeed.

The migration container requires `MIGRATION_DB_USER` and
`MIGRATION_DB_PASSWORD`. It reuses `DATABASE_HOST`, `DATABASE_PORT`, and
`MYSQL_DATABASE`, but it does not receive or fall back to the Backend's
`MYSQL_USER` or `MYSQL_PASSWORD`. Missing migration variables fail with their
names only, before any database connection or Backend activation.

`schema_migrations` records each schema filename, SHA-256 checksum, and applied
timestamp. `data_migrations` records the equivalent information for one-time
data jobs. Applied files are skipped. Changing an applied file's checksum fails
the deployment instead of rerunning it.

To add schema migration 010 or 011, create an immutable, ordered SQL file such
as `database/migrations/010_description.sql`. If it needs a one-time backfill,
add a similarly numbered Python file under `database/data_migrations/`; declare
its exact `REQUIRES_SCHEMA` filename and expose `run(connection)`. Data jobs are
deferred until their schema file exists and fail if that schema is present but
not applied.

## Team migration rule

- Every production schema change must be a new sequentially numbered file in
  `database/migrations/`, including changes to existing tables.
- An applied migration is immutable. Never edit it to make another change; use
  the next sequential migration instead.
- The runner is not a schema-diff engine. It knows only committed migration
  files and their recorded migration history.
- Manual production schema changes are outside the normal workflow and are
  reserved for emergency operator remediation.
- Migrations `001` through `008` are the manually managed legacy baseline.
  Production must be confirmed to match that baseline before automation is
  enabled; migrations `009` and later are managed automatically.

## One-time production setup

Before the automation PR is merged, the Deployment owner must:

1. confirm that production RDS matches the legacy `001` through `008` baseline;
2. create a dedicated migration database user, separate from the Backend user;
3. grant that user only the privileges required for migrations;
4. configure `MIGRATION_DB_USER` and `MIGRATION_DB_PASSWORD` in the protected
   production EC2/deployment environment;
5. confirm that the migration container can connect to RDS; and
6. only then approve the automation PR for merge.

The current migration account needs `CREATE`, `ALTER`, `SELECT`, `INSERT`, and
`DELETE`. Future migration SQL may additionally require `UPDATE`, `INDEX`,
`REFERENCES`, or another explicitly reviewed privilege. Account creation and
grants are operator responsibilities; application code does not grant them.

Migration output and failures are written to the existing production deployment
log at `/var/log/fit5120-deploy.log`. A failure produces a non-zero deployment
status before the new Backend is started.
