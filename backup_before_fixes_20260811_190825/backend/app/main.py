from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings

# Create FastAPI app
app = FastAPI(
    title="Timesheet IL Widget API",
    description="amoCRM timesheet widget with activity tracking",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Timesheet IL Widget API",
        "version": "1.0.0",
        "status": "running"
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Include routers
from app.api.v1 import sessions, team, activity, categories, settings, reports
from app.api.v1.endpoints import departments, excel, kpi

app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
app.include_router(team.router, prefix="/api/v1/team", tags=["team"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["activity"])
app.include_router(categories.router, prefix="/api/v1/categories", tags=["categories"])
app.include_router(settings.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(reports.router, prefix="/api/v1", tags=["reports"])
app.include_router(departments.router, prefix="/api/v1/departments", tags=["departments"])
app.include_router(excel.router, prefix="/api/v1/excel", tags=["excel"])
app.include_router(kpi.router, prefix="/api/v1/kpi", tags=["kpi"])
