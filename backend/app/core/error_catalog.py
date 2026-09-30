"""Stable public error messages safe to return to API clients."""

from __future__ import annotations


PUBLIC_ERRORS: dict[str, str] = {
    "AMOCRM_TOKEN_EXPIRED": "Срок подключения amoCRM истёк.",
    "ACCESS_DENIED": "У вас нет доступа к этому разделу.",
    "NOT_FOUND": "Данные не найдены.",
    "CONFLICT": "Операция конфликтует с текущим состоянием.",
    "REQUEST_INVALID": "Запрос не может быть обработан.",
    "VALIDATION_ERROR": "Проверьте формат и значения полей запроса.",
    "RATE_LIMITED": "Слишком много запросов. Повторите попытку позже.",
    "INTERNAL_ERROR": "Произошла внутренняя ошибка. Повторите попытку позже.",
}


def public_error(code: str) -> tuple[str, str]:
    """Return a known public error, falling back to the generic request error."""

    if code in PUBLIC_ERRORS:
        return code, PUBLIC_ERRORS[code]
    return "REQUEST_INVALID", PUBLIC_ERRORS["REQUEST_INVALID"]
