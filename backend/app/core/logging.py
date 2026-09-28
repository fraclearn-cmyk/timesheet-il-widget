"""Logging guards for opaque webhook credentials."""

from __future__ import annotations

import logging
import re


_WEBHOOK_PATH = re.compile(r"(/api/v1/webhooks/amocrm/)[^?\s]+")
_REDACTED_PATH = r"\1[redacted]"


def redact_webhook_path(value: object) -> object:
    if not isinstance(value, str):
        return value
    return _WEBHOOK_PATH.sub(_REDACTED_PATH, value)


class WebhookAccessLogFilter(logging.Filter):
    """Redact the request-target argument used by Uvicorn's AccessFormatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(redact_webhook_path(value) for value in record.args)
        elif isinstance(record.args, dict):
            record.args = {
                key: redact_webhook_path(value) for key, value in record.args.items()
            }
        return True


def install_webhook_access_log_filter() -> None:
    logger = logging.getLogger("uvicorn.access")
    if not any(isinstance(item, WebhookAccessLogFilter) for item in logger.filters):
        logger.addFilter(WebhookAccessLogFilter())
