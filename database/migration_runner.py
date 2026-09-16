"""Apply tracked production schema and one-time data migrations."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import importlib.util
import os
from pathlib import Path
import re
from types import ModuleType
from typing import Iterable

import pymysql
from pymysql.constants import CLIENT


MANAGED_SCHEMA_VERSION = 9
MIGRATION_LOCK_NAME = "firebreak_database_migrations"
ROOT = Path(__file__).resolve().parents[1]
SCHEMA_DIRECTORY = ROOT / "database" / "migrations"
DATA_DIRECTORY = ROOT / "database" / "data_migrations"
MIGRATION_PATTERN = re.compile(r"^(\d+)_")
SCHEMA_MIGRATION_FILENAME_PATTERN = re.compile(
    r"^\d+_[A-Za-z0-9][A-Za-z0-9_.-]*\.sql$"
)
MIGRATION_CREDENTIAL_VARIABLES = (
    "MIGRATION_DB_USER",
    "MIGRATION_DB_PASSWORD",
)


class MigrationError(RuntimeError):
    """Raised when migration safety checks or execution fail."""


@dataclass(frozen=True)
class MigrationFile:
    path: Path
    version: int
    checksum: str

    @property
    def migration_id(self) -> str:
        return self.path.name


@dataclass(frozen=True)
class DataMigrationDefinition:
    migration: MigrationFile
    module: ModuleType
    required_schema: str


def migration_credentials() -> tuple[str, str]:
    """Return dedicated migration credentials or fail without exposing values."""
    missing = [
        name for name in MIGRATION_CREDENTIAL_VARIABLES if not os.getenv(name)
    ]
    if missing:
        raise MigrationError(
            "Missing required migration environment variable(s): "
            + ", ".join(missing)
        )
    return os.environ["MIGRATION_DB_USER"], os.environ["MIGRATION_DB_PASSWORD"]


def database_connection():
    """Connect using the dedicated production migration credential."""
    user, password = migration_credentials()
    return pymysql.connect(
        host=os.getenv("DATABASE_HOST", "127.0.0.1"),
        port=int(os.getenv("DATABASE_PORT", "3306")),
        user=user,
        password=password,
        database=os.environ["MYSQL_DATABASE"],
        charset="utf8mb4",
        autocommit=False,
        client_flag=CLIENT.MULTI_STATEMENTS,
    )


def file_checksum(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_migrations(directory: Path, suffix: str) -> list[MigrationFile]:
    migrations = []
    if not directory.exists():
        return migrations
    for path in directory.iterdir():
        match = MIGRATION_PATTERN.match(path.name)
        if not path.is_file() or path.suffix != suffix or match is None:
            continue
        migrations.append(
            MigrationFile(
                path=path,
                version=int(match.group(1)),
                checksum=file_checksum(path),
            )
        )
    return sorted(
        migrations,
        key=lambda migration: (migration.version, migration.path.name),
    )


def validate_managed_schema_sequence(
    migrations: list[MigrationFile],
    *,
    require_contiguous: bool = True,
) -> None:
    by_version: dict[int, list[str]] = {}
    for migration in migrations:
        by_version.setdefault(migration.version, []).append(migration.migration_id)

    duplicates = {
        version: filenames
        for version, filenames in by_version.items()
        if len(filenames) > 1
    }
    if duplicates:
        version = min(duplicates)
        raise MigrationError(
            f"Duplicate managed schema migration numeric prefix {version:03d}: "
            + ", ".join(sorted(duplicates[version]))
        )

    if not migrations or not require_contiguous:
        return

    highest_version = max(by_version)
    missing_versions = [
        version
        for version in range(MANAGED_SCHEMA_VERSION, highest_version + 1)
        if version not in by_version
    ]
    if missing_versions:
        formatted = ", ".join(f"{version:03d}" for version in missing_versions)
        raise MigrationError(
            "Managed schema migration sequence has missing numeric prefix(es): "
            f"{formatted}; later migrations will not be executed"
        )


def managed_schema_migrations(
    directory: Path = SCHEMA_DIRECTORY,
    *,
    require_contiguous: bool = True,
) -> list[MigrationFile]:
    migrations = discover_migrations(directory, ".sql")
    legacy = [item.migration_id for item in migrations if item.version < MANAGED_SCHEMA_VERSION]
    if legacy:
        print(
            "Legacy schema baseline (not executed automatically): "
            + ", ".join(legacy)
        )
    managed = [item for item in migrations if item.version >= MANAGED_SCHEMA_VERSION]
    validate_managed_schema_sequence(
        managed,
        require_contiguous=require_contiguous,
    )
    return managed


def data_migrations(directory: Path = DATA_DIRECTORY) -> list[MigrationFile]:
    return discover_migrations(directory, ".py")


def ensure_tracking_tables(connection) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            migration_id VARCHAR(255) NOT NULL PRIMARY KEY,
            checksum CHAR(64) NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
        """,
        """
        CREATE TABLE IF NOT EXISTS data_migrations (
            migration_id VARCHAR(255) NOT NULL PRIMARY KEY,
            checksum CHAR(64) NOT NULL,
            applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB
        """,
    )
    with connection.cursor() as cursor:
        for statement in statements:
            cursor.execute(statement)
    connection.commit()


def applied_migrations(connection, table: str) -> dict[str, str]:
    if table not in {"schema_migrations", "data_migrations"}:
        raise ValueError(f"Unsupported migration table: {table}")
    with connection.cursor() as cursor:
        cursor.execute(f"SELECT migration_id, checksum FROM {table}")
        return {migration_id: checksum for migration_id, checksum in cursor.fetchall()}


def record_migration(connection, table: str, migration: MigrationFile) -> None:
    if table not in {"schema_migrations", "data_migrations"}:
        raise ValueError(f"Unsupported migration table: {table}")
    with connection.cursor() as cursor:
        cursor.execute(
            f"INSERT INTO {table} (migration_id, checksum) VALUES (%s, %s)",
            (migration.migration_id, migration.checksum),
        )


def verify_checksum(migration: MigrationFile, applied: dict[str, str]) -> bool:
    recorded = applied.get(migration.migration_id)
    if recorded is None:
        return False
    if recorded != migration.checksum:
        raise MigrationError(
            f"Checksum mismatch for applied migration {migration.migration_id}: "
            "the committed migration file was changed"
        )
    return True


def execute_sql_migration(connection, migration: MigrationFile) -> None:
    sql = migration.path.read_text(encoding="utf-8")
    if not sql.strip():
        raise MigrationError(f"Migration is empty: {migration.migration_id}")
    with connection.cursor() as cursor:
        cursor.execute(sql)
        while cursor.nextset():
            pass


def apply_schema_migrations(
    connection,
    directory: Path = SCHEMA_DIRECTORY,
    data_directory: Path = DATA_DIRECTORY,
) -> list[str]:
    migrations = managed_schema_migrations(directory, require_contiguous=False)
    validate_data_migration_schema_dependencies(data_directory, directory)
    validate_managed_schema_sequence(migrations)
    ensure_tracking_tables(connection)
    applied = applied_migrations(connection, "schema_migrations")
    executed = []
    for migration in migrations:
        if verify_checksum(migration, applied):
            print(f"Schema migration already applied: {migration.migration_id}")
            continue
        print(f"Applying schema migration: {migration.migration_id}")
        try:
            execute_sql_migration(connection, migration)
            record_migration(connection, "schema_migrations", migration)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        applied[migration.migration_id] = migration.checksum
        executed.append(migration.migration_id)
    if not executed:
        print("No pending schema migrations.")
    return executed


def load_data_migration(migration: MigrationFile) -> ModuleType:
    module_name = f"firebreak_data_migration_{migration.path.stem}_{migration.checksum[:8]}"
    spec = importlib.util.spec_from_file_location(module_name, migration.path)
    if spec is None or spec.loader is None:
        raise MigrationError(f"Could not load data migration: {migration.migration_id}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_data_migration_metadata(
    migration: MigrationFile,
    module: ModuleType,
    schema_directory: Path = SCHEMA_DIRECTORY,
) -> DataMigrationDefinition:
    required_schema = getattr(module, "REQUIRES_SCHEMA", None)
    if not isinstance(required_schema, str) or not required_schema.strip():
        raise MigrationError(
            "Data migration REQUIRES_SCHEMA must be a non-empty string: "
            f"{migration.migration_id}"
        )
    if required_schema != required_schema.strip():
        raise MigrationError(
            "Data migration REQUIRES_SCHEMA must be an exact filename without "
            f"surrounding whitespace: {migration.migration_id}"
        )
    if (
        "/" in required_schema
        or "\\" in required_schema
        or Path(required_schema).name != required_schema
        or SCHEMA_MIGRATION_FILENAME_PATTERN.fullmatch(required_schema) is None
    ):
        raise MigrationError(
            "Data migration REQUIRES_SCHEMA must name a numbered .sql file "
            f"inside database/migrations: {migration.migration_id} -> "
            f"{required_schema}"
        )

    run = getattr(module, "run", None)
    if not callable(run):
        raise MigrationError(
            f"Data migration has no callable run(connection): {migration.migration_id}"
        )

    dependency_path = schema_directory / required_schema
    if not dependency_path.is_file():
        raise MigrationError(
            f"Data migration {migration.migration_id} requires missing schema "
            f"migration {required_schema}"
        )

    return DataMigrationDefinition(
        migration=migration,
        module=module,
        required_schema=required_schema,
    )


def validate_data_migration_schema_dependencies(
    data_directory: Path,
    schema_directory: Path,
) -> None:
    """Require every data migration's schema dependency to exist."""
    for data_migration in data_migrations(data_directory):
        validate_data_migration_metadata(
            data_migration,
            load_data_migration(data_migration),
            schema_directory,
        )


def apply_data_migrations(
    connection,
    directory: Path = DATA_DIRECTORY,
    schema_directory: Path = SCHEMA_DIRECTORY,
) -> list[str]:
    ensure_tracking_tables(connection)
    applied_schema = applied_migrations(connection, "schema_migrations")
    applied_data = applied_migrations(connection, "data_migrations")
    executed = []
    migrations = data_migrations(directory)

    # Check immutable history before importing code, then validate every numbered
    # data migration definition before executing any pending job.
    for migration in migrations:
        verify_checksum(migration, applied_data)
    definitions = [
        validate_data_migration_metadata(
            migration,
            load_data_migration(migration),
            schema_directory,
        )
        for migration in migrations
    ]

    for definition in definitions:
        migration = definition.migration
        if migration.migration_id in applied_data:
            print(f"Data migration already applied: {migration.migration_id}")
            continue

        if definition.required_schema not in applied_schema:
            raise MigrationError(
                f"Data migration {migration.migration_id} requires unapplied schema "
                f"migration {definition.required_schema}"
            )

        print(f"Applying data migration: {migration.migration_id}")
        try:
            definition.module.run(connection)
            record_migration(connection, "data_migrations", migration)
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        applied_data[migration.migration_id] = migration.checksum
        executed.append(migration.migration_id)

    if not executed:
        print("No pending data migrations.")
    return executed


@contextmanager
def migration_lock(connection):
    with connection.cursor() as cursor:
        cursor.execute("SELECT GET_LOCK(%s, %s)", (MIGRATION_LOCK_NAME, 60))
        row = cursor.fetchone()
    if row is None or row[0] != 1:
        raise MigrationError("Could not acquire the production migration lock")
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT RELEASE_LOCK(%s)", (MIGRATION_LOCK_NAME,))


def run_command(command: str) -> None:
    if command == "validate":
        migration_credentials()
        print("Required migration database credentials are configured.")
        return

    connection = database_connection()
    try:
        with migration_lock(connection):
            if command in {"schema", "all"}:
                apply_schema_migrations(connection)
            if command in {"data", "all"}:
                apply_data_migrations(connection)
    finally:
        connection.close()


def parse_args(arguments: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "schema", "data", "all"))
    return parser.parse_args(arguments)


def main() -> None:
    args = parse_args()
    try:
        run_command(args.command)
    except Exception as exc:
        raise SystemExit(f"Database migration failed: {exc}") from exc


if __name__ == "__main__":
    main()
