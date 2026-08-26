# Database

MySQL 8 is the project's database and runs locally through Docker Compose.

- `init/` is reserved for database initialization scripts.
- `migrations/` is reserved for schema migration files once a migration approach is selected.
- Optional development seed data may be added later when the application domain is defined.

No application tables or seed data are defined yet. Credentials are supplied through environment variables and must not be committed.
