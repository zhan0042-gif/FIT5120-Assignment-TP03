from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def test_deploy_runs_database_work_before_backend_activation() -> None:
    script = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    checkout = "git reset --hard origin/main"
    build = "migration build migration"
    validate = "migration run --rm --no-deps migration validate"
    schema = "migration run --rm --no-deps migration schema"
    data = "migration run --rm --no-deps migration data"
    backend = "up -d --build --no-deps --wait --wait-timeout 120 backend"

    assert (
        script.index(checkout)
        < script.index(build)
        < script.index(validate)
        < script.index(schema)
        < script.index(data)
        < script.index(backend)
    )


def test_database_changes_trigger_the_production_workflow() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    assert '- "database/**"' in workflow


def test_production_deployments_are_serialized_without_cancellation() -> None:
    workflow = yaml.safe_load(
        (ROOT / ".github" / "workflows" / "deploy.yml").read_text(
            encoding="utf-8"
        )
    )
    concurrency = workflow["jobs"]["deploy"]["concurrency"]

    assert concurrency["group"] == "firebreak-production-deployment"
    assert concurrency["cancel-in-progress"] is False
    assert "concurrency" not in workflow["jobs"]["test"]


def test_compose_uses_disposable_migration_image() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'profiles: ["migration"]' in compose
    assert "dockerfile: database/Dockerfile.migrations" in compose


def test_compose_separates_migration_and_backend_credentials() -> None:
    compose = yaml.safe_load(
        (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )
    services = compose["services"]
    migration_environment = services["migration"]["environment"]
    backend_environment = services["backend"]["environment"]

    assert "MIGRATION_DB_USER" in migration_environment
    assert "MIGRATION_DB_PASSWORD" in migration_environment
    assert "MYSQL_USER" not in migration_environment
    assert "MYSQL_PASSWORD" not in migration_environment

    assert "MYSQL_USER" in backend_environment
    assert "MYSQL_PASSWORD" in backend_environment
    assert "MIGRATION_DB_USER" not in backend_environment
    assert "MIGRATION_DB_PASSWORD" not in backend_environment


def test_compose_has_no_backend_credential_fallback_for_migrations() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    migration_block = compose.split("  migration:", 1)[1].split("\n  backend:", 1)[0]

    assert "${MYSQL_USER" not in migration_block
    assert "${MYSQL_PASSWORD" not in migration_block
    assert "change_me" not in migration_block
