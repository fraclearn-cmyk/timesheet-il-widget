"""Trusted request-context dependency; browser identity fields are never production auth."""

from __future__ import annotations

import os
from secrets import compare_digest

import httpx
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.access_policy import AccessPolicy, RequestContext
from app.core.config import settings
from app.core.database import get_db
from app.integrations.amocrm_client import AmoCRMClient, AmoCRMClientError
from app.integrations.oauth import OAuthTokenCipher
from app.models.oauth_connection import OAuthConnection
from app.models.user import User, UserRole
from app.models.work_session import WorkSession
from app.models.activity_session import ActivitySession
from app.models.activity_category import ActivityCategory
from app.models.department import Department
from app.models.report import Report
from app.models.widget_group import WidgetGroup


class RequestContextUnauthorized(HTTPException):
    def __init__(self) -> None:
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AMOCRM_TOKEN_EXPIRED",
            headers={"WWW-Authenticate": "Bearer"},
        )


class APIProblem(HTTPException):
    """Stable public error contract without object-existence disclosure."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(status_code=status_code, detail=code)


def not_found() -> APIProblem:
    return APIProblem(status.HTTP_404_NOT_FOUND, "NOT_FOUND", "Данные не найдены.")


def access_denied() -> APIProblem:
    return APIProblem(
        status.HTTP_403_FORBIDDEN, "ACCESS_DENIED", "У вас нет доступа к этому разделу."
    )


def require_account(context: RequestContext, account_id: int | str) -> int:
    try:
        requested = int(account_id)
    except (TypeError, ValueError) as error:
        raise not_found() from error
    if requested != context.account_id:
        raise not_found()
    return requested


def require_visible_external_user(
    db: Session, context: RequestContext, amocrm_user_id: int
) -> User:
    target = (
        db.query(User)
        .filter(
            User.amocrm_account_id == context.account_id,
            User.amocrm_user_id == amocrm_user_id,
            User.is_active.is_(True),
        )
        .one_or_none()
    )
    try:
        return AccessPolicy(db, context).require_view_user(target)
    except (LookupError, PermissionError) as error:
        raise not_found() from error


def require_visible_internal_user(
    db: Session, context: RequestContext, reference: int | str
) -> User:
    try:
        value = int(reference)
    except (TypeError, ValueError) as error:
        raise not_found() from error
    target = (
        db.query(User)
        .filter(
            User.id == value,
            User.amocrm_account_id == context.account_id,
            User.is_active.is_(True),
        )
        .one_or_none()
    )
    try:
        return AccessPolicy(db, context).require_view_user(target)
    except (LookupError, PermissionError) as error:
        raise not_found() from error


def require_visible_user_reference(
    db: Session, context: RequestContext, reference: int | str
) -> User:
    try:
        value = int(reference)
    except (TypeError, ValueError) as error:
        raise not_found() from error
    targets = (
        db.query(User)
        .filter(
            User.amocrm_account_id == context.account_id,
            User.is_active.is_(True),
            (User.id == value) | (User.amocrm_user_id == value),
        )
        .all()
    )
    # A numeric reference can match both an internal and an external ID.  Do
    # not choose one implicitly; ambiguous identity is a closed authorization
    # failure rather than an opportunity to invent an ID mapping.
    target = targets[0] if len(targets) == 1 else None
    try:
        return AccessPolicy(db, context).require_view_user(target)
    except (LookupError, PermissionError) as error:
        raise not_found() from error


def require_self_external_user(context: RequestContext, amocrm_user_id: int) -> User:
    if context.user.amocrm_user_id != amocrm_user_id:
        raise not_found()
    return context.user


def require_self_internal_user(context: RequestContext, reference: int | str) -> User:
    if _integer_reference(reference) != context.user.id:
        raise not_found()
    return context.user


def _integer_reference(reference: int | str) -> int:
    try:
        value = int(reference)
    except (TypeError, ValueError) as error:
        raise not_found() from error
    if value <= 0:
        raise not_found()
    return value


def require_visible_work_session(
    db: Session, context: RequestContext, reference: int | str
) -> WorkSession:
    """Resolve a work session only after checking its account and user scope."""
    session = db.get(WorkSession, _integer_reference(reference))
    if session is None or session.amocrm_account_id != context.account_id:
        raise not_found()
    try:
        require_visible_external_user(db, context, session.amocrm_user_id)
    except APIProblem:
        raise
    return session


def require_visible_activity_session(
    db: Session, context: RequestContext, reference: int | str
) -> ActivitySession:
    """Activity sessions inherit visibility from their owning work session."""
    activity = db.get(ActivitySession, _integer_reference(reference))
    if activity is None:
        raise not_found()
    require_visible_work_session(db, context, activity.work_session_id)
    return activity


def require_owned_work_session(
    db: Session, context: RequestContext, reference: int | str
) -> WorkSession:
    """Resolve a work session only when the verified caller owns it."""
    session = require_visible_work_session(db, context, reference)
    if session.amocrm_user_id != context.user.amocrm_user_id:
        raise not_found()
    return session


def require_owned_activity_session(
    db: Session, context: RequestContext, reference: int | str
) -> ActivitySession:
    """Activity mutations inherit the verified caller's work-session ownership."""
    activity = require_visible_activity_session(db, context, reference)
    require_owned_work_session(db, context, activity.work_session_id)
    return activity


def require_visible_report(
    db: Session, context: RequestContext, reference: int | str
) -> Report:
    report = db.get(Report, _integer_reference(reference))
    if report is None or str(report.account_id) != str(context.account_id):
        raise not_found()
    if report.generated_by is not None:
        require_visible_internal_user(db, context, report.generated_by)
    if report.user_id is not None:
        require_visible_external_user(db, context, report.user_id)
    return report


def require_visible_department(
    db: Session, context: RequestContext, reference: int | str
) -> Department:
    """Resolve a department through its explicit account owner."""
    department_id = _integer_reference(reference)
    department = (
        db.query(Department)
        .filter(
            Department.id == department_id,
            Department.account_id == context.account_id,
            Department.is_active.is_(True),
        )
        .one_or_none()
    )
    if department is None or not AccessPolicy(db, context).can_view_department(
        department_id
    ):
        raise not_found()
    return department


def require_visible_group(
    db: Session, context: RequestContext, reference: int | str
) -> WidgetGroup:
    group = db.get(WidgetGroup, _integer_reference(reference))
    if group is None or group.account_id != context.account_id or not group.is_active:
        raise not_found()
    return group


def require_visible_category(
    db: Session, context: RequestContext, reference: int | str
) -> ActivityCategory:
    """Resolve a category by its explicit migration-007 account owner."""
    category = (
        db.query(ActivityCategory)
        .filter(
            ActivityCategory.id == _integer_reference(reference),
            ActivityCategory.account_id == context.account_id,
            ActivityCategory.is_active.is_(True),
        )
        .one_or_none()
    )
    if category is None:
        raise not_found()
    return category


def _environment() -> str:
    return os.getenv("ENVIRONMENT", settings.ENVIRONMENT).lower()


def resolve_legacy_test_context(
    db: Session, user_id: str | None, account_id: str | None
) -> RequestContext:
    """Compatibility adapter exclusively for hermetic tests; production always rejects it."""
    if _environment() not in {"test", "testing"}:
        raise RequestContextUnauthorized()
    try:
        external_user_id, external_account_id = int(user_id or ""), int(
            account_id or ""
        )
    except ValueError as error:
        raise RequestContextUnauthorized() from error
    user = (
        db.query(User)
        .filter(
            User.amocrm_user_id == external_user_id,
            User.amocrm_account_id == external_account_id,
            User.is_active.is_(True),
        )
        .one_or_none()
    )
    if user is None:
        raise RequestContextUnauthorized()
    return RequestContext(account_id=external_account_id, user=user)


async def get_request_context(
    request: Request, db: Session = Depends(get_db)
) -> RequestContext:
    """Resolve identity from verified OAuth state, with a test-only legacy adapter."""
    legacy_user = request.headers.get("X-User-Id")
    legacy_account = request.headers.get("X-Account-Id")
    if legacy_user is not None or legacy_account is not None:
        return resolve_legacy_test_context(db, legacy_user, legacy_account)
    authorization = request.headers.get("Authorization", "")
    scheme, _, access_token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not access_token:
        raise RequestContextUnauthorized()
    cipher = OAuthTokenCipher.from_secret(settings.SECRET_KEY)
    connection = None
    for candidate in db.query(OAuthConnection).filter(
        OAuthConnection.is_active.is_(True)
    ):
        try:
            stored_token = cipher.decrypt(candidate.encrypted_access_token)
        except ValueError:
            continue
        if compare_digest(stored_token, access_token):
            connection = candidate
            break
    if connection is None:
        raise RequestContextUnauthorized()
    try:
        async with httpx.AsyncClient() as http:
            client = AmoCRMClient(http)
            account = await client.get_account(connection.account_url, access_token)
            current_users = await client.list_users(
                connection.account_url, access_token
            )
    except (AmoCRMClientError, httpx.HTTPError):
        raise RequestContextUnauthorized()
    account_id, user_id = account.get("id"), account.get("current_user_id")
    if (
        account_id != connection.account_id
        or not isinstance(user_id, int)
        or user_id <= 0
    ):
        raise RequestContextUnauthorized()
    user = (
        db.query(User)
        .filter(
            User.amocrm_account_id == account_id,
            User.amocrm_user_id == user_id,
            User.is_active.is_(True),
        )
        .one_or_none()
    )
    if user is None:
        raise RequestContextUnauthorized()
    observed = next((item for item in current_users if item.get("id") == user_id), None)
    if observed is None:
        raise RequestContextUnauthorized()
    rights = observed.get("rights")
    user.amocrm_rights = dict(rights) if isinstance(rights, dict) else None
    role_id = rights.get("role_id") if isinstance(rights, dict) else None
    user.amocrm_role_id = (
        role_id if isinstance(role_id, int) and not isinstance(role_id, bool) else None
    )
    db.commit()
    # The phase-0 contract observes only rights.is_admin and opaque role_id.
    # Never invent an is_active field or interpret role_id semantics.  A local
    # admin must remain a live amoCRM admin; manager authority is decided by
    # AccessPolicy's assignment snapshot, not User.role.
    if not isinstance(rights, dict):
        raise access_denied()
    if user.role == UserRole.ADMIN and rights.get("is_admin") is not True:
        raise access_denied()
    context = RequestContext(account_id=account_id, user=user, privileges_verified=True)
    return context


async def enforce_route_scope(
    request: Request,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> RequestContext:
    """Bind legacy path/query identifiers to the verified account before handlers run."""
    values = {**request.path_params, **dict(request.query_params)}
    account = values.get("account_id")
    if account is not None:
        require_account(context, account)
    route_path = request.url.path
    if (
        "employee_id" in values
        or "/kpi/user/" in route_path
        or "/kpi/chart/user/" in route_path
    ):
        for name in ("employee_id", "target_user_id"):
            if name in values:
                require_visible_internal_user(db, context, values[name])
    else:
        for name in ("target_user_id", "user_id"):
            if name in values:
                require_visible_external_user(db, context, values[name])
    for name in ("session_id", "work_session_id"):
        if name in values:
            require_visible_work_session(db, context, values[name])
    if "activity_session_id" in values:
        require_visible_activity_session(db, context, values["activity_session_id"])
    if "report_id" in values:
        require_visible_report(db, context, values["report_id"])
    for name in ("department_id", "dept_id"):
        if name in values:
            require_visible_department(db, context, values[name])
    if "group_id" in values:
        require_visible_group(db, context, values["group_id"])
    if "category_id" in values:
        require_visible_category(db, context, values["category_id"])
    if "generated_by" in values:
        require_self_internal_user(context, values["generated_by"])
    # Body IDs are just as attacker-controlled as path/query IDs.  Starlette
    # caches request.json(), so FastAPI can still parse the same payload later.
    try:
        body = await request.json()
    except (TypeError, ValueError):
        body = None
    if isinstance(body, dict):
        if body.get("account_id") is not None:
            require_account(context, body["account_id"])
        for name in ("user_id", "target_user_id"):
            if body.get(name) is not None:
                require_visible_external_user(db, context, body[name])
        if body.get("employee_id") is not None:
            require_visible_internal_user(db, context, body["employee_id"])
        if body.get("generated_by") is not None:
            require_self_internal_user(context, body["generated_by"])
        for name in ("work_session_id", "session_id"):
            if body.get(name) is not None:
                require_visible_work_session(db, context, body[name])
        if body.get("activity_session_id") is not None:
            require_visible_activity_session(db, context, body["activity_session_id"])
        for name in ("department_id", "dept_id"):
            if body.get(name) is not None:
                require_visible_department(db, context, body[name])
        if body.get("group_id") is not None:
            require_visible_group(db, context, body["group_id"])
        if body.get("category_id") is not None:
            require_visible_category(db, context, body["category_id"])
        department_ids = body.get("department_ids")
        if department_ids is not None:
            if not isinstance(department_ids, list) or len(department_ids) > 100:
                raise APIProblem(422, "INVALID_REQUEST", "Некорректный список отделов.")
            for department_id in department_ids:
                require_visible_department(db, context, department_id)
    return context
