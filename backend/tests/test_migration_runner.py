import sys
from pathlib import Path

import pytest

from database import migration_runner
from database.migration_runner import (
    MigrationError,
    apply_data_migrations,
    apply_schema_migrations,
    database_connection,
    file_checksum,
    load_data_migration,
    migration_credentials,
    run_command,
    validate_data_migration_metadata,
)


class FakeCursor:
    def __init__(self, connection):
        self.connection = connection
        self.results = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("CREATE TABLE IF NOT EXISTS"):
            return
        if normalized.startswith("SELECT migration_id, checksum FROM"):
            table = normalized.rsplit(" ", 1)[-1]
            self.results = list(self.connection.records[table].items())
            return
        if normalized.startswith("INSERT INTO schema_migrations"):
            self.connection.records["schema_migrations"][params[0]] = params[1]
            return
        if normalized.startswith("INSERT INTO data_migrations"):
            self.connection.records["data_migrations"][params[0]] = params[1]
            return
        if "RAISE_FAILURE" in normalized:
            raise RuntimeError("migration failed")
        self.connection.executed_sql.append(normalized)

    def fetchall(self):
        return self.results

    def fetchone(self):
        return self.results[0] if self.results else None

    def nextset(self):
        return False


class FakeConnection:
    def __init__(self):
        self.records = {"schema_migrations": {}, "data_migrations": {}}
        self.executed_sql = []
        self.events = []
        self.commits = 0
        self.rollbacks = 0

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def write_schema(directory: Path, filename: str, sql: str = "SELECT 1") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(sql, encoding="utf-8")
    return path


def apply_test_schema(connection, directory: Path) -> list[str]:
    return apply_schema_migrations(
        connection,
        directory,
        data_directory=directory.parent / "no-data-migrations",
    )


def write_data_migration(
    directory: Path,
    filename: str,
    *,
    dependency: str = "009_add_fire_history_area_ha.sql",
    statement: str = "connection.events.append('data')",
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(
        f'REQUIRES_SCHEMA = "{dependency}"\n\n'
        "def run(connection):\n"
        f"    {statement}\n",
        encoding="utf-8",
    )
    return path


def test_migration_credentials_require_dedicated_user(monkeypatch) -> None:
    monkeypatch.delenv("MIGRATION_DB_USER", raising=False)
    monkeypatch.setenv("MIGRATION_DB_PASSWORD", "migration-password")
    monkeypatch.setenv("MYSQL_USER", "backend-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "backend-password")

    with pytest.raises(MigrationError) as error:
        migration_credentials()

    assert "MIGRATION_DB_USER" in str(error.value)
    assert "backend-user" not in str(error.value)
    assert "backend-password" not in str(error.value)


def test_migration_credentials_require_dedicated_password(monkeypatch) -> None:
    monkeypatch.setenv("MIGRATION_DB_USER", "migration-user")
    monkeypatch.delenv("MIGRATION_DB_PASSWORD", raising=False)
    monkeypatch.setenv("MYSQL_USER", "backend-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "backend-password")

    with pytest.raises(MigrationError) as error:
        migration_credentials()

    assert "MIGRATION_DB_PASSWORD" in str(error.value)
    assert "backend-password" not in str(error.value)


def test_migration_credentials_do_not_fall_back_to_backend(monkeypatch) -> None:
    monkeypatch.delenv("MIGRATION_DB_USER", raising=False)
    monkeypatch.delenv("MIGRATION_DB_PASSWORD", raising=False)
    monkeypatch.setenv("MYSQL_USER", "backend-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "backend-password")

    with pytest.raises(MigrationError) as error:
        migration_credentials()

    message = str(error.value)
    assert "MIGRATION_DB_USER" in message
    assert "MIGRATION_DB_PASSWORD" in message
    assert "backend-user" not in message
    assert "backend-password" not in message


def test_database_connection_uses_dedicated_migration_credentials(
    monkeypatch,
) -> None:
    captured = {}
    expected_connection = object()

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return expected_connection

    monkeypatch.setenv("MIGRATION_DB_USER", "migration-user")
    monkeypatch.setenv("MIGRATION_DB_PASSWORD", "migration-password")
    monkeypatch.setenv("MYSQL_USER", "backend-user")
    monkeypatch.setenv("MYSQL_PASSWORD", "backend-password")
    monkeypatch.setenv("MYSQL_DATABASE", "fit5120")
    monkeypatch.setattr(migration_runner.pymysql, "connect", fake_connect)

    assert database_connection() is expected_connection
    assert captured["user"] == "migration-user"
    assert captured["password"] == "migration-password"


def test_validate_command_does_not_connect(monkeypatch) -> None:
    monkeypatch.setenv("MIGRATION_DB_USER", "migration-user")
    monkeypatch.setenv("MIGRATION_DB_PASSWORD", "migration-password")

    def unexpected_connect(**_kwargs):
        raise AssertionError("validate must not connect to the database")

    monkeypatch.setattr(migration_runner.pymysql, "connect", unexpected_connect)

    run_command("validate")


def test_pending_schema_migration_executes_once(tmp_path) -> None:
    schema = tmp_path / "schema"
    migration = write_schema(schema, "009_create_example.sql", "SELECT 'nine'")
    connection = FakeConnection()

    assert apply_test_schema(connection, schema) == [migration.name]
    assert apply_test_schema(connection, schema) == []
    assert connection.executed_sql.count("SELECT 'nine'") == 1


def test_failed_schema_migration_is_not_recorded(tmp_path) -> None:
    schema = tmp_path / "schema"
    migration = write_schema(schema, "009_failure.sql", "RAISE_FAILURE")
    connection = FakeConnection()

    with pytest.raises(RuntimeError, match="migration failed"):
        apply_test_schema(connection, schema)

    assert migration.name not in connection.records["schema_migrations"]
    assert connection.rollbacks == 1


def test_applied_schema_checksum_mismatch_fails(tmp_path) -> None:
    schema = tmp_path / "schema"
    migration = write_schema(schema, "009_checksum.sql", "SELECT 1")
    connection = FakeConnection()
    apply_test_schema(connection, schema)
    migration.write_text("SELECT 2", encoding="utf-8")

    with pytest.raises(MigrationError, match="Checksum mismatch"):
        apply_test_schema(connection, schema)


def test_existing_table_changes_use_new_immutable_migrations(tmp_path) -> None:
    schema = tmp_path / "schema"
    migration_009 = write_schema(schema, "009_initial_managed_schema.sql")
    migration_010 = write_schema(
        schema,
        "010_add_column_to_existing_table.sql",
        "ALTER TABLE existing_table ADD COLUMN note VARCHAR(100)",
    )
    original_010 = migration_010.read_text(encoding="utf-8")
    connection = FakeConnection()

    assert apply_test_schema(connection, schema) == [
        migration_009.name,
        migration_010.name,
    ]
    assert apply_test_schema(connection, schema) == []
    assert connection.executed_sql.count(original_010) == 1

    migration_010.write_text(
        "ALTER TABLE existing_table ADD COLUMN edited_after_apply INT",
        encoding="utf-8",
    )
    with pytest.raises(MigrationError, match="Checksum mismatch"):
        apply_test_schema(connection, schema)
    assert len(connection.executed_sql) == 2

    migration_010.write_text(original_010, encoding="utf-8")
    migration_011 = write_schema(
        schema,
        "011_change_existing_table_again.sql",
        """
        ALTER TABLE existing_table MODIFY COLUMN note VARCHAR(255);
        CREATE INDEX idx_existing_note ON existing_table (note);
        DROP INDEX idx_existing_note ON existing_table;
        ALTER TABLE existing_table
            ADD CONSTRAINT fk_existing_parent
            FOREIGN KEY (parent_id) REFERENCES parent_table(id)
        """,
    )

    assert apply_test_schema(connection, schema) == [migration_011.name]
    assert any("MODIFY COLUMN" in sql for sql in connection.executed_sql)
    assert any("CREATE INDEX" in sql for sql in connection.executed_sql)
    assert any("DROP INDEX" in sql for sql in connection.executed_sql)
    assert any("ADD CONSTRAINT" in sql for sql in connection.executed_sql)


def test_schema_migrations_run_in_filename_order(tmp_path) -> None:
    schema = tmp_path / "schema"
    write_schema(schema, "011_third.sql", "SELECT 'third'")
    write_schema(schema, "009_first.sql", "SELECT 'first'")
    write_schema(schema, "010_second.sql", "SELECT 'second'")
    connection = FakeConnection()

    apply_test_schema(connection, schema)

    assert connection.executed_sql == [
        "SELECT 'first'",
        "SELECT 'second'",
        "SELECT 'third'",
    ]


def test_unique_consecutive_managed_schema_ids_are_valid(tmp_path) -> None:
    schema = tmp_path / "schema"
    migration_009 = write_schema(schema, "009_first.sql")
    migration_010 = write_schema(schema, "010_second.sql")
    connection = FakeConnection()

    assert apply_test_schema(connection, schema) == [
        migration_009.name,
        migration_010.name,
    ]


def test_duplicate_managed_schema_numeric_prefix_fails(tmp_path) -> None:
    schema = tmp_path / "schema"
    write_schema(schema, "009_first.sql")
    write_schema(schema, "010_change_a.sql")
    write_schema(schema, "010_change_b.sql")
    connection = FakeConnection()

    with pytest.raises(MigrationError, match="Duplicate.*010"):
        apply_test_schema(connection, schema)

    assert connection.executed_sql == []


def test_managed_schema_numbering_gap_fails_before_execution(tmp_path) -> None:
    schema = tmp_path / "schema"
    write_schema(schema, "009_first.sql")
    write_schema(schema, "011_third.sql")
    connection = FakeConnection()

    with pytest.raises(MigrationError, match="missing numeric prefix.*010"):
        apply_test_schema(connection, schema)

    assert connection.executed_sql == []


def test_schema_command_fails_when_data_dependency_is_missing(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    write_data_migration(
        data,
        "009_backfill.py",
        dependency="009_future.sql",
    )
    connection = FakeConnection()

    with pytest.raises(MigrationError, match="requires missing schema migration"):
        apply_schema_migrations(connection, schema, data)

    assert connection.executed_sql == []
    assert connection.records["data_migrations"] == {}


def test_data_dependency_validation_succeeds_after_schema_lands(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    migration_009 = write_schema(schema, "009_future.sql", "SELECT 'nine'")
    migration_010 = write_schema(schema, "010_later.sql", "SELECT 'ten'")
    write_data_migration(
        data,
        "009_backfill.py",
        dependency=migration_009.name,
    )
    connection = FakeConnection()

    assert apply_schema_migrations(connection, schema, data) == [
        migration_009.name,
        migration_010.name,
    ]
    assert connection.executed_sql == ["SELECT 'nine'", "SELECT 'ten'"]


def test_legacy_schema_migrations_are_never_executed(tmp_path) -> None:
    schema = tmp_path / "schema"
    write_schema(schema, "002_legacy.sql", "SELECT 'legacy'")
    write_schema(schema, "008_legacy.sql", "SELECT 'legacy-eight'")
    connection = FakeConnection()

    assert apply_test_schema(connection, schema) == []
    assert connection.executed_sql == []
    assert connection.records["schema_migrations"] == {}


def test_no_pending_schema_migrations_is_successful_no_op(tmp_path) -> None:
    connection = FakeConnection()

    assert apply_test_schema(connection, tmp_path / "missing") == []
    assert connection.records["schema_migrations"] == {}


def test_pending_data_migration_executes_once(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    schema_file = write_schema(schema, "009_add_fire_history_area_ha.sql")
    migration = write_data_migration(data, "009_backfill_fire_history_area.py")
    connection = FakeConnection()
    connection.records["schema_migrations"][schema_file.name] = file_checksum(
        schema_file
    )

    assert apply_data_migrations(connection, data, schema) == [migration.name]
    assert apply_data_migrations(connection, data, schema) == []
    assert connection.events == ["data"]


def test_failed_data_migration_is_not_recorded(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    schema_file = write_schema(schema, "009_add_fire_history_area_ha.sql")
    migration = write_data_migration(
        data,
        "009_backfill_fire_history_area.py",
        statement="raise RuntimeError('backfill failed')",
    )
    connection = FakeConnection()
    connection.records["schema_migrations"][schema_file.name] = file_checksum(
        schema_file
    )

    with pytest.raises(RuntimeError, match="backfill failed"):
        apply_data_migrations(connection, data, schema)

    assert migration.name not in connection.records["data_migrations"]
    assert connection.rollbacks == 1


def test_applied_data_checksum_mismatch_fails(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    schema_file = write_schema(schema, "009_add_fire_history_area_ha.sql")
    migration = write_data_migration(data, "009_backfill_fire_history_area.py")
    connection = FakeConnection()
    connection.records["schema_migrations"][schema_file.name] = file_checksum(
        schema_file
    )
    apply_data_migrations(connection, data, schema)
    migration.write_text(migration.read_text() + "\n# changed\n", encoding="utf-8")

    with pytest.raises(MigrationError, match="Checksum mismatch"):
        apply_data_migrations(connection, data, schema)


def test_missing_schema_dependency_fails_without_execution_or_recording(tmp_path) -> None:
    data = tmp_path / "data"
    migration = write_data_migration(data, "009_backfill.py")
    connection = FakeConnection()

    with pytest.raises(MigrationError, match="requires missing schema migration"):
        apply_data_migrations(connection, data, tmp_path / "schema")

    assert connection.events == []
    assert migration.name not in connection.records["data_migrations"]


def test_misspelled_schema_dependency_fails(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    write_schema(schema, "009_expected_schema.sql")
    write_data_migration(
        data,
        "009_backfill.py",
        dependency="009_expected_schmea.sql",
    )
    connection = FakeConnection()

    with pytest.raises(MigrationError, match="009_expected_schmea.sql"):
        apply_data_migrations(connection, data, schema)


def test_cli_exits_nonzero_for_accidental_missing_schema(
    tmp_path,
    monkeypatch,
) -> None:
    data = tmp_path / "data"
    missing_schema = "009_missing_schema.sql"
    write_data_migration(data, "009_backfill.py", dependency=missing_schema)
    connection = FakeConnection()

    def run_fixture(_command):
        apply_data_migrations(connection, data, tmp_path / "schema")

    monkeypatch.setattr(migration_runner, "run_command", run_fixture)
    monkeypatch.setattr(sys, "argv", ["migration_runner", "data"])

    with pytest.raises(SystemExit, match=missing_schema):
        migration_runner.main()


@pytest.mark.parametrize(
    "metadata_source",
    [
        "def run(connection):\n    pass\n",
        'REQUIRES_SCHEMA = ""\n\ndef run(connection):\n    pass\n',
        "REQUIRES_SCHEMA = 9\n\ndef run(connection):\n    pass\n",
    ],
)
def test_data_migration_metadata_rejects_malformed_required_schema(
    tmp_path,
    metadata_source,
) -> None:
    data = tmp_path / "data"
    data.mkdir()
    migration_path = data / "009_bad_metadata.py"
    migration_path.write_text(metadata_source, encoding="utf-8")
    migration = migration_runner.data_migrations(data)[0]

    with pytest.raises(MigrationError, match="non-empty string"):
        validate_data_migration_metadata(
            migration,
            load_data_migration(migration),
            tmp_path / "schema",
        )


@pytest.mark.parametrize(
    "dependency",
    [
        "../009_outside.sql",
        "subdirectory/009_outside.sql",
        "..\\009_outside.sql",
        "009_not_sql.txt",
    ],
)
def test_data_migration_metadata_rejects_paths_outside_schema_directory(
    tmp_path,
    dependency,
) -> None:
    data = tmp_path / "data"
    migration_path = write_data_migration(
        data,
        "009_bad_path.py",
        dependency=dependency,
    )
    migration = migration_runner.data_migrations(data)[0]

    with pytest.raises(MigrationError, match="inside database/migrations"):
        validate_data_migration_metadata(
            migration,
            load_data_migration(migration),
            tmp_path / "schema",
        )

    assert migration_path.exists()


def test_repository_009_backfill_requires_existing_schema() -> None:
    schema_path = (
        migration_runner.SCHEMA_DIRECTORY
        / "009_add_fire_history_area_ha.sql"
    )
    migration = next(
        item
        for item in migration_runner.data_migrations()
        if item.migration_id == "009_backfill_fire_history_area.py"
    )
    definition = validate_data_migration_metadata(
        migration,
        load_data_migration(migration),
    )

    assert definition.required_schema == schema_path.name
    assert schema_path.is_file()


def test_data_migration_fails_when_required_schema_is_present_but_unapplied(
    tmp_path,
) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    write_schema(schema, "009_add_fire_history_area_ha.sql")
    write_data_migration(data, "009_backfill_fire_history_area.py")
    connection = FakeConnection()

    with pytest.raises(MigrationError, match="requires unapplied schema"):
        apply_data_migrations(connection, data, schema)

    assert connection.events == []


def test_data_migrations_run_in_filename_order(tmp_path) -> None:
    schema = tmp_path / "schema"
    data = tmp_path / "data"
    schema_009 = write_schema(schema, "009_schema.sql")
    schema_010 = write_schema(schema, "010_schema.sql")
    write_data_migration(
        data,
        "010_second.py",
        dependency=schema_010.name,
        statement="connection.events.append('second')",
    )
    write_data_migration(
        data,
        "009_first.py",
        dependency=schema_009.name,
        statement="connection.events.append('first')",
    )
    connection = FakeConnection()
    connection.records["schema_migrations"] = {
        schema_009.name: file_checksum(schema_009),
        schema_010.name: file_checksum(schema_010),
    }

    apply_data_migrations(connection, data, schema)

    assert connection.events == ["first", "second"]
