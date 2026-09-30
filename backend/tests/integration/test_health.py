from pathlib import Path
import os
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


EXPECTED_HEAD = "013"


@pytest.fixture
def migrated_db(monkeypatch):
    admin_url = os.getenv("TEST_POSTGRES_ADMIN_URL")
    if not admin_url:
        pytest.skip("TEST_POSTGRES_ADMIN_URL required for disposable PostgreSQL tests")
    url = make_url(admin_url)
    assert url.get_backend_name() == "postgresql"
    name = "timesheet_health_test_" + uuid4().hex
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{name}"'))
    database_url = url.set(database=name)
    from app.core.config import settings

    monkeypatch.setattr(
        settings, "DATABASE_URL", database_url.render_as_string(hide_password=False)
    )
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[2] / "migrations")
    )
    engine = create_engine(database_url)
    try:
        yield config, engine
    finally:
        engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{name}" WITH (FORCE)'))
        admin.dispose()


def test_liveness_remains_available_when_database_is_unavailable(monkeypatch):
    import app.main as main

    class BrokenEngine:
        def connect(self):
            raise RuntimeError("postgresql://user:super-secret@db/private")

    monkeypatch.setattr(main, "database_engine", BrokenEngine())
    response = TestClient(main.app).get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_readiness_is_unavailable_without_database_and_hides_error(monkeypatch):
    import app.main as main

    class BrokenEngine:
        def connect(self):
            raise RuntimeError("postgresql://user:super-secret@db/private")

    monkeypatch.setattr(main, "database_engine", BrokenEngine())
    response = TestClient(main.app).get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {
        "status": "not_ready",
        "checks": {"database": "unavailable", "schema": "unknown"},
    }
    assert "super-secret" not in response.text


def test_readiness_rejects_schema_behind_expected_head(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "012")

    from app.main import readiness_status

    status_code, payload = readiness_status(engine, expected_head=EXPECTED_HEAD)

    assert status_code == 503
    assert payload == {
        "status": "not_ready",
        "checks": {"database": "ready", "schema": "not_ready"},
    }


def test_readiness_accepts_disposable_postgres_at_expected_head(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("select version_num from alembic_version"))
            == EXPECTED_HEAD
        )

    from app.main import readiness_status

    status_code, payload = readiness_status(engine, expected_head=EXPECTED_HEAD)

    assert status_code == 200
    assert payload == {
        "status": "ready",
        "checks": {"database": "ready", "schema": "ready"},
    }


def test_readiness_rejects_multiple_database_heads(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                "insert into alembic_version (version_num) values ('unexpected_branch')"
            )
        )

    from app.main import readiness_status

    status_code, payload = readiness_status(engine, expected_head=EXPECTED_HEAD)

    assert status_code == 503
    assert payload["checks"] == {"database": "ready", "schema": "not_ready"}


def test_expected_head_is_read_from_the_migration_graph():
    from app.main import expected_alembic_head

    assert expected_alembic_head() == EXPECTED_HEAD


def test_single_head_check_tracks_a_future_migration_without_code_constant():
    from app.main import single_alembic_head

    class FutureMigrationGraph:
        def get_heads(self):
            return ["014"]

    assert single_alembic_head(FutureMigrationGraph()) == "014"


def test_single_head_check_rejects_branched_migration_graph():
    from app.main import single_alembic_head

    class BranchedMigrationGraph:
        def get_heads(self):
            return ["014_a", "014_b"]

    with pytest.raises(RuntimeError, match="exactly one"):
        single_alembic_head(BranchedMigrationGraph())
