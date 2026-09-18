from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.user import User
from app.models.work_session import WorkSession
from app.models.activity_session import ActivitySession, EntityType
from app.models.report import Report, ReportType, ReportFormat
from app.models.department import Department
from datetime import datetime


def _client(monkeypatch):
    from app.core.database import get_db
    from app.main import app

    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all(
        [
            User(id=1, amocrm_user_id=10, amocrm_account_id=20, name="Self"),
            User(id=2, amocrm_user_id=11, amocrm_account_id=20, name="Other"),
        ]
    )
    db.commit()
    monkeypatch.setenv("ENVIRONMENT", "test")
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app), app


def test_settings_rejects_a_forged_account_path_without_existence_leak(monkeypatch):
    """Using path account_id instead of RequestContext must fail this authorization test."""
    client, app = _client(monkeypatch)
    try:
        response = client.get(
            "/api/v1/settings/21", headers={"X-User-Id": "10", "X-Account-Id": "20"}
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_session_mutation_rejects_another_employee_before_service_execution(
    monkeypatch,
):
    """Replacing self-only target validation with a service call would expose mutation."""
    client, app = _client(monkeypatch)
    try:
        response = client.post(
            "/api/v1/sessions/break/11",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_rate_limit_uses_the_standard_429_error_body():
    """Returning a legacy detail-only rate-limit response must fail this API contract."""
    from app.main import RateLimitMiddleware

    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, calls_per_minute=1)

    @app.get("/")
    def root():
        return {"ok": True}

    client = TestClient(app)
    assert client.get("/").status_code == 200
    response = client.get("/")
    assert response.status_code == 429
    assert response.json()["error"]["code"] == "RATE_LIMITED"


def test_duplicate_session_returns_normalized_conflict(monkeypatch):
    """Mapping a session state conflict to 400 would hide a retryable conflict from clients."""
    client, app = _client(monkeypatch)
    headers = {"X-User-Id": "10", "X-Account-Id": "20"}
    try:
        assert (
            client.post(
                "/api/v1/sessions/start",
                json={"user_id": 10, "user_name": "Self"},
                headers=headers,
            ).status_code
            == 201
        )
        response = client.post(
            "/api/v1/sessions/start",
            json={"user_id": 10, "user_name": "Self"},
            headers=headers,
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "SESSION_CONFLICT"
    finally:
        app.dependency_overrides.clear()


def test_activity_work_session_path_rejects_foreign_session_before_handler(monkeypatch):
    """Activity routes must scope work_session_id, not only the /sessions routes."""
    client, app = _client(monkeypatch)
    from app.core.database import get_db
    db = app.dependency_overrides[get_db]()
    db.add(
        WorkSession(
            id=40,
            amocrm_user_id=11,
            amocrm_account_id=20,
            user_name="Other",
            start_time=datetime.utcnow(),
        )
    )
    db.commit()
    try:
        response = client.get(
            "/api/v1/activity/current/40",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_activity_session_path_rejects_foreign_session_before_handler(monkeypatch):
    """Activity session IDs inherit ownership from their work session."""
    client, app = _client(monkeypatch)
    from app.core.database import get_db
    db = app.dependency_overrides[get_db]()
    db.add(
        WorkSession(
            id=41,
            amocrm_user_id=11,
            amocrm_account_id=20,
            user_name="Other",
            start_time=datetime.utcnow(),
        )
    )
    db.add(
        ActivitySession(
            id=42,
            work_session_id=41,
            entity_type=EntityType.LEAD,
            entity_id=7,
            start_time=datetime.utcnow(),
        )
    )
    db.commit()
    try:
        response = client.get(
            "/api/v1/activity/events/42",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_report_path_rejects_foreign_report_before_handler(monkeypatch):
    """Saved reports must be account-scoped by their own account column."""
    client, app = _client(monkeypatch)
    from app.core.database import get_db
    db = app.dependency_overrides[get_db]()
    db.add(
        Report(
            id=50,
            report_type=ReportType.DAILY,
            report_format=ReportFormat.JSON,
            title="Other account",
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            account_id="21",
            data={},
            generated_by=11,
        )
    )
    db.commit()
    try:
        response = client.get(
            "/api/v1/reports/50",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_department_path_rejects_unowned_department_before_handler(monkeypatch):
    """Department IDs without an active user in this account are not addressable."""
    client, app = _client(monkeypatch)
    from app.core.database import get_db
    db = app.dependency_overrides[get_db]()
    db.add(
        Department(
            id=60,
            name="Other department",
            work_start_time=datetime.strptime("09:00", "%H:%M").time(),
            work_end_time=datetime.strptime("18:00", "%H:%M").time(),
        )
    )
    db.commit()
    try:
        response = client.get(
            "/api/v1/departments/60/schedule",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_excel_body_rejects_unowned_department_before_handler(monkeypatch):
    """JSON body department IDs must receive the same scope check as path IDs."""
    client, app = _client(monkeypatch)
    try:
        response = client.post(
            "/api/v1/excel/department",
            json={
                "date_from": "2026-09-01",
                "date_to": "2026-09-18",
                "department_ids": [999],
            },
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"
    finally:
        app.dependency_overrides.clear()


def test_activity_history_limit_is_bounded(monkeypatch):
    """Legacy activity history must not accept an unbounded item request."""
    client, app = _client(monkeypatch)
    from app.core.database import get_db
    db = app.dependency_overrides[get_db]()
    db.add(
        WorkSession(
            id=70,
            amocrm_user_id=10,
            amocrm_account_id=20,
            user_name="Self",
            start_time=datetime.utcnow(),
        )
    )
    db.commit()
    try:
        response = client.get(
            "/api/v1/activity/history/70?limit=1001",
            headers={"X-User-Id": "10", "X-Account-Id": "20"},
        )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
