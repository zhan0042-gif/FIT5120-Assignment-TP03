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
its exact `REQUIRES_SCHEMA` filename and expose `run(connection)`. A missing
schema file or a schema migration that has not been applied is a hard failure.

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

## Compatibility and destructive changes

Schema migrations run before the new Backend is activated, while the previous
Backend may still be serving requests. A migration must therefore normally
remain compatible with that old Backend. Safe defaults include adding a table,
adding a nullable column, or adding a compatible index.

Dropping or renaming columns/tables, incompatible type changes, or removing
constraints/data still used by the running Backend requires an
expand/migrate/contract rollout. Deployment A adds the new structure and ships
Backend code that can work while the old structure remains. A later deployment,
after old code no longer depends on it, removes the obsolete structure through
a new migration.

Keep migrations small and forward-only, preferably one logical DDL change per
file. MySQL DDL may not be transactionally reversible, so a partial DDL failure
can require Deployment/operator remediation.

## Data migration dependencies

Every numbered data migration must reference an existing schema migration by
its exact filename. A missing dependency stops deployment before the data job
can run or be recorded. The referenced schema migration must also be recorded
as applied before its data migration executes.

## One-time production setup

Before the automation PR is merged, the Deployment owner must:

1. confirm that production RDS matches the legacy `001` through `008` baseline;
2. create a dedicated migration database user, separate from the Backend user;
3. grant that user only the privileges required for migrations;
4. configure `MIGRATION_DB_USER` and `MIGRATION_DB_PASSWORD` in the protected
   production EC2/deployment environment;
5. confirm that the migration container can connect to RDS; and
6. only then approve the automation PR for merge.

The migration/deployment account privilege envelope is `SELECT`, `INSERT`,
`UPDATE`, `DELETE`, `CREATE`, `ALTER`, `DROP`, `INDEX`, and `REFERENCES`. These
are not Backend runtime privileges. The Deployment owner must review each
migration and grant only the privileges needed by its SQL; for example, `DROP`,
`INDEX`, or `REFERENCES` is needed only when the migration performs that kind of
operation. Account creation and grants are operator responsibilities;
application code does not grant them. The Backend account remains separate.

Migration output and failures are written to the existing production deployment
log at `/var/log/fit5120-deploy.log`. A failure produces a non-zero deployment
status before the new Backend is started.

## When a migration fails partway

MySQL does not roll back DDL: every CREATE, ALTER or DROP commits immediately,
so a multi-statement migration that fails halfway leaves the schema in a partial
state. The migration is only recorded after every statement succeeds, so the
failed run is not recorded and the next deploy retries the same file, failing
again on the first statement that had already been applied.

Recovery is manual and forward-only:

1. Read the failure in /var/log/fit5120-deploy.log to find the last statement
   that succeeded.
2. Connect to RDS and inspect the affected objects.
3. Either apply the remaining statements by hand, or undo the applied ones. Note
   that undoing an applied statement can lose data.
4. Do not edit the migration file. If it was wrong, add a new numbered migration.
5. If the schema cannot be reconciled by hand, restore the RDS snapshot taken
   before the change. This returns the whole database, application data
   included, to that point in time, so it is the last resort.
6. The next deploy re-runs the file and records it.
