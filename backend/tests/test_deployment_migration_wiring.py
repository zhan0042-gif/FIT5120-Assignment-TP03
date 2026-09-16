from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_deploy_runs_database_work_before_backend_activation() -> None:
    script = (ROOT / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    schema = "migration run --rm --no-deps migration schema"
    data = "migration run --rm --no-deps migration data"
    backend = "up -d --build --no-deps --wait --wait-timeout 120 backend"

    assert script.index(schema) < script.index(data) < script.index(backend)


def test_database_changes_trigger_the_production_workflow() -> None:
    workflow = (ROOT / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )

    assert '- "database/**"' in workflow


def test_compose_uses_disposable_migration_image() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert 'profiles: ["migration"]' in compose
    assert "dockerfile: database/Dockerfile.migrations" in compose
