"""Strict verification for amoCRM disposable widget JWTs."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import UUID

from jose import JWTError, jwt


class WidgetTokenInvalid(ValueError):
    """A widget token failed verification without exposing token details."""


@dataclass(frozen=True)
class WidgetTokenClaims:
    account_id: int
    user_id: int
    issuer: str
    token_id: str


def _positive_int(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise WidgetTokenInvalid("widget token is invalid")
    return value


def _trusted_amocrm_origin(value: object) -> str:
    if not isinstance(value, str) or value.strip() != value:
        raise WidgetTokenInvalid("widget token is invalid")
    try:
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError as error:
        raise WidgetTokenInvalid("widget token is invalid") from error
    host = parsed.hostname.lower() if parsed.hostname else ""
    allowed_suffixes = (".amocrm.ru", ".amocrm.com", ".kommo.com")
    is_single_tenant = any(
        host.endswith(suffix)
        and host[: -len(suffix)]
        and "." not in host[: -len(suffix)]
        for suffix in allowed_suffixes
    )
    if (
        parsed.scheme != "https"
        or not is_single_tenant
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.path not in ("", "/")
        or parsed.query
        or parsed.fragment
    ):
        raise WidgetTokenInvalid("widget token is invalid")
    return f"https://{host}"


def decode_widget_token(
    token: str, *, secret: str, audience: str, client_uuid: str
) -> WidgetTokenClaims:
    """Verify and normalize an amoCRM disposable widget token."""
    try:
        payload = jwt.decode(
            token,
            secret,
            algorithms=["HS256"],
            audience=audience,
            options={
                "require_exp": True,
                "require_iat": True,
                "require_nbf": True,
                "require_jti": True,
                "require_aud": True,
            },
        )
        if payload.get("client_uuid") != client_uuid:
            raise WidgetTokenInvalid("widget token is invalid")
        return WidgetTokenClaims(
            account_id=_positive_int(payload.get("account_id")),
            user_id=_positive_int(payload.get("user_id")),
            issuer=_trusted_amocrm_origin(payload.get("iss")),
            token_id=str(UUID(payload["jti"])),
        )
    except (JWTError, KeyError, TypeError, ValueError) as error:
        raise WidgetTokenInvalid("widget token is invalid") from error
