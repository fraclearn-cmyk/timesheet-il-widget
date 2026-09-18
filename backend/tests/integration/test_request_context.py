import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.v1.dependencies import (
    RequestContextUnauthorized,
    resolve_legacy_test_context,
)
from app.core.database import Base
from app.models.user import User


def test_legacy_identity_headers_fail_closed_outside_test_environment(monkeypatch):
    """Accepting forged X-User-Id/X-Account-Id in production must fail."""
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="User"))
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "production")

    with pytest.raises(RequestContextUnauthorized):
        resolve_legacy_test_context(db, "10", "20")


def test_legacy_identity_headers_resolve_only_the_matching_active_test_user(
    monkeypatch,
):
    """Dropping account or active predicates would authenticate the wrong principal."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="Active"),
            User(id=2, amocrm_user_id=10, amocrm_account_id=21, name="Other account"),
        ]
    )
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "test")

    context = resolve_legacy_test_context(db, "10", "20")

    assert context.account_id == 20
    assert context.user.id == 1


def test_me_requires_context_and_ignores_forged_query_identity(monkeypatch):
    """A missing context or a browser-supplied account must not select the principal."""
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="Active"))
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "test")
    app.dependency_overrides[get_db] = lambda: db
    client = TestClient(app)
    try:
        assert client.get("/api/v1/me").status_code == 401
        response = client.get(
            "/api/v1/me?account_id=999&user_id=999",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 200
        assert response.json()["account_id"] == 20
        assert response.json()["user"]["amocrm_id"] == 10
    finally:
        app.dependency_overrides.clear()
