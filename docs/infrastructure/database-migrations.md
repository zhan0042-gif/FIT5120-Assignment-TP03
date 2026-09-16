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
2. applies pending files in `database/migrations/` in filename order;
3. runs eligible one-time jobs in `database/data_migrations/`; and
4. starts Backend only after both migration commands succeed.

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

Migration output and failures are written to the existing production deployment
log at `/var/log/fit5120-deploy.log`. A failure produces a non-zero deployment
status before the new Backend is started.
