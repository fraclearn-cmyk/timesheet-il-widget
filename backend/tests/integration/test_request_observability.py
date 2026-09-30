import json
import logging
from uuid import UUID, uuid4

from fastapi.testclient import TestClient


def _as_uuid(value: str) -> UUID:
    parsed = UUID(value)
    assert str(parsed) == value
    return parsed


def test_server_generates_one_request_id_for_response_and_error_body():
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/missing-observability-probe")

    request_id = response.headers["X-Request-Id"]
    _as_uuid(request_id)
    assert response.status_code == 404
    assert response.json()["error"]["request_id"] == request_id


def test_only_a_canonical_bounded_uuid_is_accepted_from_the_client():
    from app.main import app

    trusted = str(uuid4())
    malicious = "not-a-uuid\r\nX-Forged: yes" + "x" * 200
    with TestClient(app) as client:
        accepted = client.get(
            "/missing-observability-probe", headers={"X-Request-Id": trusted}
        )
        rejected = client.get(
            "/missing-observability-probe", headers={"X-Request-Id": malicious}
        )

    assert accepted.headers["X-Request-Id"] == trusted
    assert accepted.json()["error"]["request_id"] == trusted
    replacement = rejected.headers["X-Request-Id"]
    _as_uuid(replacement)
    assert replacement != malicious
    assert rejected.json()["error"]["request_id"] == replacement
    assert "X-Forged" not in rejected.text


def test_cors_preflight_also_receives_a_correlated_request_id():
    from app.main import app

    with TestClient(app) as client:
        response = client.options(
            "/api/v1/me",
            headers={
                "Origin": "https://tenant.amocrm.ru",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "X-Request-Id",
            },
        )

    assert response.status_code == 200
    _as_uuid(response.headers["X-Request-Id"])
    assert response.headers["Access-Control-Allow-Origin"] == "https://tenant.amocrm.ru"


def test_json_log_has_required_fields_and_current_request_id():
    from app.core.logging import JSONLogFormatter, request_id_context

    stream = __import__("io").StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONLogFormatter())
    logger = logging.Logger("observability.contract")
    logger.addHandler(handler)
    token = request_id_context.set(str(uuid4()))
    try:
        logger.info("report_exported", extra={"account_id": 40})
    finally:
        request_id_context.reset(token)

    payload = json.loads(stream.getvalue())
    assert payload["timestamp"].endswith("Z")
    assert payload["level"] == "INFO"
    assert payload["logger"] == "observability.contract"
    assert payload["event"] == "report_exported"
    _as_uuid(payload["request_id"])
    assert payload["account_id"] == 40


def test_unexpected_exception_returns_only_safe_catalog_error_and_logs_request_id(
    caplog,
):
    from fastapi import FastAPI
    from fastapi.middleware.cors import CORSMiddleware

    from app.core.error_catalog import PUBLIC_ERRORS
    from app.core.middleware import RequestContextMiddleware, SafeExceptionMiddleware

    probe = FastAPI()
    probe.add_middleware(SafeExceptionMiddleware)
    probe.add_middleware(
        CORSMiddleware,
        allow_origins=["https://tenant.amocrm.ru"],
        allow_methods=["GET"],
        expose_headers=["X-Request-Id"],
    )
    probe.add_middleware(RequestContextMiddleware)

    @probe.get("/boom")
    def boom():
        raise RuntimeError("password=do-not-return-or-log")

    error_logger = logging.getLogger("app.errors")
    error_logger.disabled = True  # Alembic fileConfig can disable existing loggers.
    try:
        with caplog.at_level(logging.ERROR, logger="app.errors"):
            response = TestClient(probe, raise_server_exceptions=False).get(
                "/boom", headers={"Origin": "https://tenant.amocrm.ru"}
            )
    finally:
        error_logger.disabled = False

    request_id = response.headers["X-Request-Id"]
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": PUBLIC_ERRORS["INTERNAL_ERROR"],
            "request_id": request_id,
        }
    }
    assert "do-not-return-or-log" not in response.text
    assert response.headers["Access-Control-Allow-Origin"] == "https://tenant.amocrm.ru"
    assert any(record.request_id == request_id for record in caplog.records)
    assert all(record.exc_info is None for record in caplog.records)
