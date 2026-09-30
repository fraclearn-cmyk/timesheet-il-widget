import json
import logging


def test_recursive_redaction_covers_credentials_and_webhook_identifiers():
    from app.core.logging import REDACTED, redact_secrets

    value = {
        "Authorization": "Bearer abc",
        "headers": {"Cookie": "session=abc"},
        "token": "abc",
        "password": "abc",
        "client_secret": "abc",
        "clientSecret": "camel-secret",
        "accessToken": "camel-token",
        "webhook_url": "https://elsewhere.invalid/callback/opaque",
        "callbackUrl": "https://elsewhere.invalid/hooks/opaque",
        "webhookId": "camel-hook",
        "nested": [
            {"hook_id": "opaque-hook"},
            "https://public.example/api/v1/webhooks/amocrm/opaque-hook",
        ],
        "safe": {"account_id": 40},
    }

    redacted = redact_secrets(value)

    assert redacted["Authorization"] == REDACTED
    assert redacted["headers"]["Cookie"] == REDACTED
    assert redacted["token"] == REDACTED
    assert redacted["password"] == REDACTED
    assert redacted["client_secret"] == REDACTED
    assert redacted["clientSecret"] == REDACTED
    assert redacted["accessToken"] == REDACTED
    assert redacted["webhook_url"] == REDACTED
    assert redacted["callbackUrl"] == REDACTED
    assert redacted["webhookId"] == REDACTED
    assert redacted["nested"][0]["hook_id"] == REDACTED
    assert "opaque-hook" not in redacted["nested"][1]
    assert redacted["safe"] == {"account_id": 40}
    assert redact_secrets("POST https://elsewhere.invalid/callback/opaque") == (
        "POST [redacted]"
    )


def test_json_formatter_redacts_nested_extra_and_exception_text():
    from app.core.logging import JSONLogFormatter

    stream = __import__("io").StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(JSONLogFormatter())
    logger = logging.Logger("security.contract")
    logger.addHandler(handler)

    try:
        raise RuntimeError(
            "client_secret=visible-secret Cookie: session=visible-cookie"
        )
    except RuntimeError:
        logger.exception(
            "upstream_failed",
            extra={
                "context": {
                    "Authorization": "Bearer visible-token",
                    "url": "https://host/api/v1/webhooks/amocrm/visible-hook",
                }
            },
        )

    output = stream.getvalue()
    payload = json.loads(output)
    assert "visible-secret" not in output
    assert "visible-token" not in output
    assert "visible-hook" not in output
    assert "visible-cookie" not in output
    assert payload["context"]["Authorization"] == "[redacted]"
    assert payload["exception"]["type"] == "RuntimeError"


def test_public_error_catalog_is_stable_russian_text():
    from app.core.error_catalog import PUBLIC_ERRORS, public_error

    assert public_error("INTERNAL_ERROR") == (
        "INTERNAL_ERROR",
        "Произошла внутренняя ошибка. Повторите попытку позже.",
    )
    assert public_error("UNKNOWN") == (
        "REQUEST_INVALID",
        PUBLIC_ERRORS["REQUEST_INVALID"],
    )
