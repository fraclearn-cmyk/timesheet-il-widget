from contextlib import asynccontextmanager
import asyncio
from functools import lru_cache
from pathlib import Path
import socket

from alembic.config import Config
from alembic.script import ScriptDirectory
import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
import time
from app.api.v1.dependencies import enforce_route_scope, get_request_context
from app.api.v1.dependencies import APIProblem
from app.core.access_policy import AccessPolicy
from app.core.database import engine as database_engine, get_db
from app.core.error_catalog import PUBLIC_ERRORS, public_error
from app.core.logging import install_json_logging, install_webhook_access_log_filter
from app.core.middleware import (
    RequestContextMiddleware,
    SafeExceptionMiddleware,
    request_id_for,
)
from app.core.rate_limit import (
    BoundedSlidingWindowLimiter,
    trusted_remote_key,
    unknown_request_limiter,
)
from app.integrations.http_transport import (
    build_amocrm_async_transport,
    build_amocrm_sync_transport,
)

try:
    from app.core.config import settings
except ImportError:
    # Fallback for testing
    class Settings:
        DEBUG = True
        ALLOWED_ORIGINS = []
        RATE_LIMIT_CALLS = 60
        RATE_LIMIT_MAX_BUCKETS = 4096
        AUTHENTICATION_MAX_CONCURRENT_PER_IP = 64

    settings = Settings()


install_json_logging()
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

        limits = httpx.Limits(
            max_connections=settings.INGESTION_MAX_CONCURRENT_ACCOUNTS,
            max_keepalive_connections=settings.INGESTION_MAX_CONCURRENT_ACCOUNTS,
        )
        sync_http = httpx.Client(
            transport=build_amocrm_sync_transport(settings.AMOCRM_LOCAL_ADDRESS)
        )
        async_http = httpx.AsyncClient(
            transport=build_amocrm_async_transport(
                settings.AMOCRM_LOCAL_ADDRESS, limits=limits
            ),
            limits=limits,
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
    """Bound public routes by socket IP; protected APIs limit verified identity."""

    def __init__(
        self,
        app,
        calls_per_minute: int = 60,
        max_clients: int = 4096,
        public_only: bool = False,
    ):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.max_clients = max_clients
        self.public_only = public_only
        self._limiter = BoundedSlidingWindowLimiter(
            calls_per_period=calls_per_minute,
            period_seconds=60,
            max_buckets=max_clients,
        )
        self.requests = self._limiter.requests

    def record_request(self, client_ip: str, *, now: float) -> bool:
        limited, _ = self._limiter.check(client_ip, now=now)
        return limited

    async def dispatch(self, request: Request, call_next):
        if self.public_only and request.url.path.startswith("/api/v1/"):
            response = await call_next(request)
            # Protected and webhook handlers set an ingress marker. Unknown paths
            # and method mismatches have neither, so they use the bounded IP pool.
            if not getattr(request.state, "ingress_guarded", False):
                limited, retry_after = unknown_request_limiter.check(
                    trusted_remote_key(request)
                )
                if limited:
                    return _rate_limited_response(request, retry_after)
            return response
        client_ip = trusted_remote_key(request)
        current_time = time.time()

        if self.record_request(client_ip, now=current_time):
            return _rate_limited_response(request, 60)

        response = await call_next(request)
        return response


def _rate_limited_response(request: Request, retry_after: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        headers={"Retry-After": str(retry_after)},
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": PUBLIC_ERRORS["RATE_LIMITED"],
                "request_id": request_id_for(request),
            }
        },
    )


# Create app
app = FastAPI(
    title="Timesheet IL API",
    version="1.0.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)


@app.exception_handler(StarletteHTTPException)
async def api_error_handler(request: Request, exc: StarletteHTTPException):
    if isinstance(exc, APIProblem):
        code, message = exc.code, exc.message
    elif exc.status_code == 401:
        code, message = public_error("AMOCRM_TOKEN_EXPIRED")
    elif exc.status_code == 403:
        code, message = public_error("ACCESS_DENIED")
    elif exc.status_code == 404:
        code, message = public_error("NOT_FOUND")
    elif exc.status_code == 409:
        code, message = public_error("CONFLICT")
    else:
        code, message = public_error("REQUEST_INVALID")
    request_id = request_id_for(request)
    response_headers = dict(exc.headers or {})
    response_headers["X-Request-Id"] = request_id
    return JSONResponse(
        status_code=exc.status_code,
        headers=response_headers,
        content={
            "error": {
                "code": code,
                "message": message,
                "request_id": request_id,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(
    request: Request, exc: RequestValidationError
):
    request_id = request_id_for(request)
    return JSONResponse(
        status_code=422,
        headers={"X-Request-Id": request_id},
        content={
            "error": {
                "code": "REQUEST_INVALID",
                "message": PUBLIC_ERRORS["VALIDATION_ERROR"],
                "request_id": request_id,
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
    app.add_middleware(
        RateLimitMiddleware,
        calls_per_minute=settings.RATE_LIMIT_CALLS,
        max_clients=settings.RATE_LIMIT_MAX_BUCKETS,
        public_only=True,
    )

# Unexpected route failures are normalized inside CORS.
app.add_middleware(SafeExceptionMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=AMOCRM_TENANT_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Auth-Token", "X-Request-Id"],
    expose_headers=["Retry-After", "X-Request-Id"],
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


# Correlation is outermost so even CORS preflight receives a request ID.
app.add_middleware(RequestContextMiddleware)


@app.get("/")
async def root():
    return {"message": "Timesheet IL API", "version": "1.0.0", "status": "running"}


def single_alembic_head(script_directory) -> str:
    heads = script_directory.get_heads()
    if len(heads) != 1:
        raise RuntimeError("Migration graph must have exactly one Alembic head")
    return heads[0]


@lru_cache(maxsize=1)
def expected_alembic_head() -> str:
    backend_root = Path(__file__).resolve().parents[1]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return single_alembic_head(ScriptDirectory.from_config(config))


def readiness_status(engine, *, expected_head: str | None = None):
    if expected_head is None:
        try:
            expected_head = expected_alembic_head()
        except Exception:
            expected_head = ""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            try:
                current_heads = list(
                    connection.scalars(text("SELECT version_num FROM alembic_version"))
                )
            except Exception:
                current_heads = []
    except Exception:
        return 503, {
            "status": "not_ready",
            "checks": {"database": "unavailable", "schema": "unknown"},
        }

    schema_status = "ready" if current_heads == [expected_head] else "not_ready"
    status = "ready" if schema_status == "ready" else "not_ready"
    return (200 if status == "ready" else 503), {
        "status": status,
        "checks": {"database": "ready", "schema": schema_status},
    }


@app.get("/health")
@app.get("/health/live")
async def health():
    return {"status": "healthy", "timestamp": time.time()}


@app.get("/health/ready")
async def readiness():
    status_code, payload = readiness_status(database_engine)
    return JSONResponse(status_code=status_code, content=payload)


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
