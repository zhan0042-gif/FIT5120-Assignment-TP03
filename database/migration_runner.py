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
    return sorted(migrations, key=lambda migration: migration.path.name)


def managed_schema_migrations(directory: Path = SCHEMA_DIRECTORY) -> list[MigrationFile]:
    migrations = discover_migrations(directory, ".sql")
    legacy = [item.migration_id for item in migrations if item.version < MANAGED_SCHEMA_VERSION]
    if legacy:
        print(
            "Legacy schema baseline (not executed automatically): "
            + ", ".join(legacy)
        )
    return [item for item in migrations if item.version >= MANAGED_SCHEMA_VERSION]


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
) -> list[str]:
    ensure_tracking_tables(connection)
    applied = applied_migrations(connection, "schema_migrations")
    executed = []
    for migration in managed_schema_migrations(directory):
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


def apply_data_migrations(
    connection,
    directory: Path = DATA_DIRECTORY,
    schema_directory: Path = SCHEMA_DIRECTORY,
) -> list[str]:
    ensure_tracking_tables(connection)
    applied_schema = applied_migrations(connection, "schema_migrations")
    applied_data = applied_migrations(connection, "data_migrations")
    schema_files = {
        migration.migration_id
        for migration in managed_schema_migrations(schema_directory)
    }
    executed = []

    for migration in data_migrations(directory):
        if verify_checksum(migration, applied_data):
            print(f"Data migration already applied: {migration.migration_id}")
            continue

        module = load_data_migration(migration)
        required_schema = getattr(module, "REQUIRES_SCHEMA", None)
        if not required_schema:
            raise MigrationError(
                f"Data migration has no REQUIRES_SCHEMA: {migration.migration_id}"
            )
        if required_schema not in schema_files:
            print(
                f"Data migration deferred because {required_schema} is not present: "
                f"{migration.migration_id}"
            )
            continue
        if required_schema not in applied_schema:
            raise MigrationError(
                f"Data migration {migration.migration_id} requires unapplied schema "
                f"migration {required_schema}"
            )
        run = getattr(module, "run", None)
        if not callable(run):
            raise MigrationError(
                f"Data migration has no callable run(connection): {migration.migration_id}"
            )

        print(f"Applying data migration: {migration.migration_id}")
        try:
            run(connection)
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
