from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time
import os

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
            t for t in self.requests.get(client_ip, [])
            if current_time - t < 60
        ]
        
        # Check limit
        if len(self.requests.get(client_ip, [])) >= self.calls_per_minute:
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"}
            )
        
        # Add request
        if client_ip not in self.requests:
            self.requests[client_ip] = []
        self.requests[client_ip].append(current_time)
        
        response = await call_next(request)
        return response


# Create app
app = FastAPI(
    title="Timesheet IL API",
    version="1.0.0",
    docs_url="/api/docs"
)

# CORS - Production secure
ALLOWED_ORIGINS = [
    "https://*.amocrm.ru",
    "https://*.amocrm.com",
]

if hasattr(settings, 'ALLOWED_ORIGINS') and settings.ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.extend(settings.ALLOWED_ORIGINS)

if hasattr(settings, 'DEBUG') and settings.DEBUG:
    ALLOWED_ORIGINS.extend(["http://localhost:3000", "http://localhost:8000"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    max_age=600,
)

# Rate limiting
if not getattr(settings, 'DEBUG', False):
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
    if not getattr(settings, 'DEBUG', False):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"
    
    return response


@app.get("/")
async def root():
    return {"message": "Timesheet IL API", "version": "1.0.0", "status": "running"}


@app.get("/health")
async def health():
    return {"status": "healthy", "timestamp": time.time()}


# Include routers
try:
    from app.api.v1 import sessions, team, activity, categories, settings as settings_router, reports
    from app.api.v1.endpoints import departments, excel, kpi
    
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(team.router, prefix="/api/v1/team", tags=["team"])
    app.include_router(activity.router, prefix="/api/v1/activity", tags=["activity"])
    app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])
    app.include_router(settings_router.router, prefix="/api/v1/settings", tags=["settings"])
    app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
    app.include_router(departments.router, prefix="/api/v1/departments", tags=["departments"])
    app.include_router(excel.router, prefix="/api/v1/excel", tags=["excel"])
    app.include_router(kpi.router, prefix="/api/v1/kpi", tags=["kpi"])
except ImportError as e:
    print(f"⚠️  Warning: Some routers not imported: {e}")
