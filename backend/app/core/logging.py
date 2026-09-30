"""Structured logging with request correlation and recursive secret redaction."""

from __future__ import annotations

from collections.abc import Mapping
from contextvars import ContextVar
from datetime import datetime, timezone
import json
import logging
import re
import sys
from typing import Any


REDACTED = "[redacted]"
request_id_context: ContextVar[str] = ContextVar("request_id", default="")

_WEBHOOK_PATH = re.compile(r"(/api/v1/webhooks/amocrm/)[^?\s]+")
_HOOK_URL = re.compile(r"(?i)https?://[^\s\"']*(?:webhook|callback|/hooks?/)[^\s\"']*")
_BEARER = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_HEADER_SECRET = re.compile(
    r"(?i)\b(authorization|cookie|set-cookie)\s*[:=]\s*[^\r\n]*"
)
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(password|passwd|token|access[_-]?token|refresh[_-]?token|secret|"
    r"client[_-]?secret|hook[_-]?id|webhook[_-]?id)\s*[:=]\s*[^\s,;]+"
)
_URL_CREDENTIALS = re.compile(r"(?i)(https?://[^:/\s]+:)[^@/\s]+@")

_STANDARD_LOG_RECORD_FIELDS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "message",
    "module",
    "msecs",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


def _redact_text(value: str) -> str:
    value = _WEBHOOK_PATH.sub(r"\1[redacted]", value)
    value = _HOOK_URL.sub(REDACTED, value)
    value = _HEADER_SECRET.sub(lambda match: f"{match.group(1)}=[redacted]", value)
    value = _BEARER.sub("Bearer [redacted]", value)
    value = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=[redacted]", value)
    return _URL_CREDENTIALS.sub(r"\1[redacted]@", value)


def _is_sensitive_key(key: object) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
    if normalized in {"authorization", "cookie", "setcookie"}:
        return True
    return normalized.endswith(
        (
            "token",
            "password",
            "passwd",
            "secret",
            "hookid",
            "webhookid",
            "webhookkey",
            "webhookurl",
            "callbackid",
            "callbackurl",
        )
    )


def redact_secrets(value: Any) -> Any:
    """Return a JSON-safe recursively redacted copy of logging data."""

    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_key(key) else redact_secrets(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [redact_secrets(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_text(str(value))


def redact_webhook_path(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _WEBHOOK_PATH.sub(r"\1[redacted]", value)


class JSONLogFormatter(logging.Formatter):
    """Emit a stable JSON object and include only safe record extras."""

    def format(self, record: logging.LogRecord) -> str:
        request_id = getattr(record, "request_id", None) or request_id_context.get()
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "event": redact_secrets(record.getMessage()),
            "request_id": request_id,
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_LOG_RECORD_FIELDS and key not in payload:
                payload[key] = redact_secrets(value)
        if record.exc_info:
            payload["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": redact_secrets(str(record.exc_info[1])),
            }
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not getattr(record, "request_id", None):
            record.request_id = request_id_context.get()
        return True


class WebhookAccessLogFilter(RequestContextFilter):
    """Redact the request-target argument used by Uvicorn's AccessFormatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        super().filter(record)
        if isinstance(record.args, tuple):
            record.args = tuple(redact_secrets(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = redact_secrets(record.args)
        return True


def install_json_logging() -> None:
    """Use JSON on configured runtime handlers without replacing test capture."""

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JSONLogFormatter())
        handler.addFilter(RequestContextFilter())
        root.addHandler(handler)
        root.setLevel(logging.INFO)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        for handler in logger.handlers:
            handler.setFormatter(JSONLogFormatter())
            if not any(
                isinstance(item, RequestContextFilter) for item in handler.filters
            ):
                handler.addFilter(RequestContextFilter())


def install_webhook_access_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, WebhookAccessLogFilter) for item in logger.filters):
        logger.addFilter(WebhookAccessLogFilter())
