from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
from app.api.v1.dependencies import enforce_route_scope, get_request_context
from fastapi import HTTPException
from app.api.v1.dependencies import APIProblem
from app.core.access_policy import AccessPolicy
from app.core.database import get_db

try:
    from app.core.config import settings
except ImportError:
    # Fallback for testing
    class Settings:
        DEBUG = True
        ALLOWED_ORIGINS = []

    settings = Settings()


# Rate limiting middleware
class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, calls_per_minute: int = 60):
        super().__init__(app)
        self.calls_per_minute = calls_per_minute
        self.requests = {}

    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean old requests
        self.requests[client_ip] = [
            t for t in self.requests.get(client_ip, []) if current_time - t < 60
        ]

        # Check limit
        if len(self.requests.get(client_ip, [])) >= self.calls_per_minute:
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

        # Add request
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append(current_time)

        response = await call_next(request)
        return response


# Create app
app = FastAPI(title="Timesheet IL API", version="1.0.0", docs_url="/api/docs")


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


# CORS - Production secure
AMOCRM_TENANT_ORIGIN_REGEX = (
    r"^https://[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\."
    r"(?:amocrm\.ru|amocrm\.com|kommo\.com)$"
)
ALLOWED_ORIGINS = list(getattr(settings, "ALLOWED_ORIGINS", []))

if hasattr(settings, "DEBUG") and settings.DEBUG:
    ALLOWED_ORIGINS.extend(["http://localhost:3000", "http://localhost:8000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=AMOCRM_TENANT_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Auth-Token"],
    max_age=600,
)

# Rate limiting
if not getattr(settings, "DEBUG", False):
    app.add_middleware(RateLimitMiddleware, calls_per_minute=60)


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
        team.router, prefix="/api/v1/team", tags=["team"], dependencies=protected
    )
    app.include_router(
        activity.router,
        prefix="/api/v1/activity",
        tags=["activity"],
        dependencies=protected,
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
