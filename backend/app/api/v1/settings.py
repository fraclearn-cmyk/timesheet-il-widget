from fastapi import APIRouter, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from app.api.v1.dependencies import access_denied, get_request_context
from app.core.access_policy import AccessPolicy, RequestContext
from app.core.database import get_db
from app.schemas.settings_snapshot import (
    SettingsSnapshotResponse,
    SettingsSnapshotUpdate,
)
from app.services.settings_snapshot_service import (
    SettingsProblem,
    SettingsSnapshotService,
)


class SettingsRoute(APIRoute):
    """Keep snapshot field errors stable without changing other API contracts."""

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def handle(request):
            try:
                return await handler(request)
            except SettingsProblem as problem:
                return JSONResponse(
                    status_code=problem.status, content={"error": problem.error}
                )
            except RequestValidationError as problem:
                first = problem.errors()[0]
                field = ".".join(str(part) for part in first["loc"] if part != "body")
                return JSONResponse(
                    status_code=422,
                    content={
                        "error": {
                            "code": "SETTINGS_INVALID",
                            "message": "Некорректное значение поля.",
                            "field": field,
                        }
                    },
                )

        return handle


router = APIRouter(route_class=SettingsRoute)


@router.get("/snapshot", response_model=SettingsSnapshotResponse)
def get_settings_snapshot(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SettingsSnapshotResponse:
    if not AccessPolicy(db, context).is_admin():
        raise access_denied()
    return SettingsSnapshotService(db).load(context)


@router.put("/snapshot", response_model=SettingsSnapshotResponse)
def put_settings_snapshot(
    payload: SettingsSnapshotUpdate,
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> SettingsSnapshotResponse:
    if not AccessPolicy(db, context).is_admin():
        raise access_denied()
    return SettingsSnapshotService(db).save(context, payload)
