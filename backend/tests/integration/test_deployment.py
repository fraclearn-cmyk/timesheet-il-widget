from pathlib import Path

import yaml
import pytest

from app.core.config import Settings


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _settings(**overrides):
    values = {
        "DATABASE_URL": "postgresql://timesheet:strong-password@db/timesheet",
        "AMOCRM_CLIENT_ID": "synthetic-client-id",
        "AMOCRM_CLIENT_SECRET": "synthetic-client-secret",
        "AMOCRM_REDIRECT_URI": "https://example.invalid/callback",
        "SECRET_KEY": "synthetic-secret-key-with-at-least-32-characters",
        "ENVIRONMENT": "production",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def _compose():
    return yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    )


def test_production_compose_has_no_weak_database_defaults_or_public_db_port():
    database = _compose()["services"]["db"]

    assert "ports" not in database
    environment = database["environment"]
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"):
        assert ":?" in environment[name]
        assert ":-postgres" not in environment[name]


def test_production_backend_has_no_source_bind_mount_or_reload():
    backend = _compose()["services"]["backend"]

    serialized = yaml.safe_dump(backend)
    assert "./backend:/app" not in serialized
    assert "--reload" not in serialized
    assert "DATABASE_URL" in backend["environment"]
    assert ":?" in backend["environment"]["DATABASE_URL"]


def test_compose_waits_for_database_and_checks_backend_readiness():
    services = _compose()["services"]

    assert services["backend"]["depends_on"]["db"]["condition"] == "service_healthy"
    healthcheck = services["backend"]["healthcheck"]
    assert "/health/ready" in " ".join(healthcheck["test"])


def test_image_runs_as_non_root_and_migrates_before_api_start():
    dockerfile = (REPOSITORY_ROOT / "backend" / "Dockerfile").read_text(
        encoding="utf-8"
    )
    entrypoint = (REPOSITORY_ROOT / "backend" / "docker-entrypoint.sh").read_text(
        encoding="utf-8"
    )

    assert "USER appuser" in dockerfile
    assert "ENTRYPOINT" in dockerfile
    assert "docker-entrypoint.sh" in dockerfile
    assert "alembic upgrade head" in entrypoint
    assert entrypoint.index("alembic upgrade head") < entrypoint.index('exec "$@"')


def test_environment_template_contains_names_without_real_secrets():
    template = (REPOSITORY_ROOT / "backend" / ".env.example").read_text(
        encoding="utf-8"
    )

    for name in (
        "DATABASE_URL",
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "AMOCRM_CLIENT_ID",
        "AMOCRM_CLIENT_SECRET",
        "SECRET_KEY",
    ):
        assert f"{name}=" in template
    assert "timesheet123" not in template
    assert "change_this" not in template
    assert "postgres:postgres" not in template


def test_docker_build_context_excludes_local_secrets():
    patterns = {
        line.strip()
        for line in (REPOSITORY_ROOT / "backend" / ".dockerignore")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }

    assert {
        ".env",
        ".env.*",
        "*.pem",
        "*.key",
        "*.crt",
        "secrets/",
        "credentials/",
    } <= patterns


def test_production_configuration_requires_postgresql():
    with pytest.raises(ValueError, match="PostgreSQL"):
        _settings(DATABASE_URL="sqlite://")


def test_test_configuration_may_use_sqlite():
    assert (
        _settings(DATABASE_URL="sqlite://", ENVIRONMENT="test").DATABASE_URL
        == "sqlite://"
    )
