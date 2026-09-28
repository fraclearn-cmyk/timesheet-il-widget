from contextlib import asynccontextmanager
import asyncio
from collections import OrderedDict
import socket

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from app.api.v1.dependencies import enforce_route_scope, get_request_context
from fastapi import HTTPException
from app.api.v1.dependencies import APIProblem
from app.core.access_policy import AccessPolicy
from app.core.database import get_db
from app.core.logging import install_webhook_access_log_filter

try:
    from app.core.config import settings
except ImportError:
    # Fallback for testing
    class Settings:
        DEBUG = True
        ALLOWED_ORIGINS = []

    settings = Settings()


install_webhook_access_log_filter()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Start one cancellable scheduler without delaying request startup."""
    resources = None
    task = None
    if getattr(settings, "INGESTION_WORKER_ENABLED", False):
        from app.core.database import SessionLocal
        from app.integrations.amocrm_client import AmoCRMClient
        from app.integrations.amocrm_contract import AmoCRMAuthClient
        from app.integrations.oauth import OAuthService, OAuthTokenCipher
        from app.services.activity_interval_service import ActivityIntervalService
        from app.services.event_ingestion_service import EventIngestionService
        from app.services.ingestion_worker import (
            DatabaseIngestionRuntime,
            IngestionWorker,
        )

        sync_http = httpx.Client()
        async_http = httpx.AsyncClient(
            limits=httpx.Limits(
                max_connections=settings.INGESTION_MAX_CONCURRENT_ACCOUNTS,
                max_keepalive_connections=settings.INGESTION_MAX_CONCURRENT_ACCOUNTS,
            )
        )
        cipher = OAuthTokenCipher.from_secret(settings.SECRET_KEY)
        auth = AmoCRMAuthClient(
            client_id=settings.AMOCRM_CLIENT_ID,
            client_secret=settings.AMOCRM_CLIENT_SECRET,
            redirect_uri=settings.AMOCRM_REDIRECT_URI,
            http_client=sync_http,
        )
        api_client = AmoCRMClient(async_http)

        def ingestion_factory(db):
            return EventIngestionService(
                db,
                api_client,
                OAuthService(db, auth, cipher),
                owner=f"{socket.gethostname()}:{id(application)}",
                poll_interval_seconds=settings.EVENT_POLL_INTERVAL_SECONDS,
            )

        runtime = DatabaseIngestionRuntime(
            session_factory=SessionLocal,
            ingestion_factory=ingestion_factory,
            presence_factory=ActivityIntervalService,
        )
        worker = IngestionWorker(
            runtime,
            runtime,
            interval_seconds=settings.EVENT_POLL_INTERVAL_SECONDS,
            max_concurrent_accounts=settings.INGESTION_MAX_CONCURRENT_ACCOUNTS,
            account_budget_seconds=10,
        )
        resources = (worker, sync_http, async_http)
        task = asyncio.create_task(worker.run(), name="amocrm-ingestion-worker")
    try:
        yield
    finally:
        if resources is not None:
            worker, sync_http, async_http = resources
            await worker.stop()
            if task is not None:
                if not task.done():
                    task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            await async_http.aclose()
            sync_http.close()


# Rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls_per_minute: int = 60, max_clients: int = 4096):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.max_clients = max_clients
        self.requests = OrderedDict()

    def record_request(self, client_ip: str, *, now: float) -> bool:
        bucket = self.requests.get(client_ip)
        if bucket is None:
            if len(self.requests) >= self.max_clients:
                self.requests.popitem(last=False)
            bucket = []
            self.requests[client_ip] = bucket
        else:
            self.requests.move_to_end(client_ip)
        bucket[:] = [timestamp for timestamp in bucket if now - timestamp < 60]
        if len(bucket) >= self.calls_per_minute:
            return True
        bucket.append(now)
        return False

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        if self.record_request(client_ip, now=current_time):
            return JSONResponse(
                status_code=429,
                headers={"Retry-After": "60"},
                content={
                    "error": {
                        "code": "RATE_LIMITED",
                        "message": "Слишком много запросов. Повторите попытку позже.",
                        "request_id": request.headers.get("X-Request-Id", ""),
                    }
                },
            )

        response = await call_next(request)
        return response


# Create app
app = FastAPI(
    title="Timesheet IL API",
    version="1.0.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)


@app.exception_handler(HTTPException)
async def api_error_handler(request: Request, exc: HTTPException):
    if isinstance(exc, APIProblem):
        code, message = exc.code, exc.message
    elif exc.status_code == 401:
        code, message = "AMOCRM_TOKEN_EXPIRED", "Срок подключения amoCRM истёк."
    elif exc.status_code == 403:
        code, message = "ACCESS_DENIED", "У вас нет доступа к этому разделу."
    elif exc.status_code == 404:
        code, message = "NOT_FOUND", "Данные не найдены."
    elif exc.status_code == 409:
        code, message = "CONFLICT", "Операция конфликтует с текущим состоянием."
    else:
        code, message = "REQUEST_INVALID", "Запрос не может быть обработан."
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request.headers.get("X-Request-Id", ""),
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "REQUEST_INVALID",
                "message": "Проверьте формат и значения полей запроса.",
                "request_id": request.headers.get("X-Request-Id", ""),
            }
        },
    )


# CORS - Production secure
AMOCRM_TENANT_ORIGIN_REGEX = (
    r"^https://[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\."
    r"(?:amocrm\.ru|amocrm\.com|kommo\.com)$"
)
ALLOWED_ORIGINS = list(getattr(settings, "ALLOWED_ORIGINS", []))

if hasattr(settings, "DEBUG") and settings.DEBUG:
    ALLOWED_ORIGINS.extend(["http://localhost:3000", "http://localhost:8000"])

# Rate limiting sits inside CORS so its 429 response is readable by the widget.
if not getattr(settings, "DEBUG", False):
    app.add_middleware(RateLimitMiddleware, calls_per_minute=60)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=AMOCRM_TENANT_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Auth-Token"],
    expose_headers=["Retry-After"],
    max_age=600,
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)

    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # CSP
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://*.amocrm.ru; "
        "style-src 'self' 'unsafe-inline'; "
    )

    # HSTS in production
    if not getattr(settings, "DEBUG", False):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"

    return response


@app.get("/")
async def root():
    return {"message": "Timesheet IL API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/api/v1/me")
async def me(context=Depends(get_request_context), db=Depends(get_db)):
    """Return identity solely from the verified server-side request context."""
    policy = AccessPolicy(db, context)
    is_admin = policy.is_admin()
    is_manager = policy.is_manager()
    return {
        "account_id": context.account_id,
        "user": {
            "amocrm_id": context.user.amocrm_user_id,
            "name": context.user.name,
            "role": context.user.role.value,
        },
        "permissions": {
            "can_configure": is_admin,
            "can_view_all_groups": is_admin,
            "can_view_own_group": is_admin or is_manager,
        },
    }


# Include routers
try:
    from app.api.v1 import (
        sessions,
        team,
        activity,
        categories,
        settings as settings_router,
        users as settings_users,
        groups as settings_groups,
        reports,
        timesheet,
        webhooks,
    )
    from app.api.v1.endpoints import departments, excel, kpi

    protected = [Depends(enforce_route_scope)]
    app.include_router(
        sessions.router,
        prefix="/api/v1/sessions",
        tags=["sessions"],
        dependencies=protected,
    )
    app.include_router(
        timesheet.router,
        prefix="/api/v1/timesheet",
        tags=["timesheet"],
        dependencies=protected,
    )
    app.include_router(
        team.router, prefix="/api/v1/team", tags=["team"], dependencies=protected
    )
    app.include_router(
        activity.router,
        prefix="/api/v1/activity",
        tags=["activity"],
        dependencies=protected,
    )
    # The opaque webhook path is intentionally outside amoCRM request auth.
    app.include_router(
        webhooks.router,
        prefix="/api/v1/webhooks",
        tags=["webhooks"],
    )
    app.include_router(
        categories.router,
        prefix="/api/v1/categories",
        tags=["categories"],
        dependencies=protected,
    )
    app.include_router(
        settings_router.router,
        prefix="/api/v1/settings",
        tags=["settings"],
        dependencies=protected,
    )
    app.include_router(
        settings_users.router,
        prefix="/api/v1/settings/users",
        tags=["settings"],
        dependencies=protected,
    )
    app.include_router(
        settings_groups.router,
        prefix="/api/v1/settings/groups",
        tags=["settings"],
        dependencies=protected,
    )
    app.include_router(
        reports.router, prefix="/api/v1", tags=["reports"], dependencies=protected
    )
    app.include_router(
        departments.router,
        prefix="/api/v1/departments",
        tags=["departments"],
        dependencies=protected,
    )
    app.include_router(
        excel.router, prefix="/api/v1/excel", tags=["excel"], dependencies=protected
    )
    app.include_router(
        kpi.router, prefix="/api/v1/kpi", tags=["kpi"], dependencies=protected
    )
except ImportError as e:
    print(f"⚠️  Warning: Some routers not imported: {e}")
