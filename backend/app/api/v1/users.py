from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import access_denied, get_request_context
from app.core.access_policy import AccessPolicy, RequestContext
from app.core.database import get_db
from app.schemas.settings_snapshot import SettingsUser
from app.services.settings_snapshot_service import SettingsSnapshotService

router = APIRouter()


@router.get("", response_model=list[SettingsUser])
def get_settings_users(
    db: Session = Depends(get_db),
    context: RequestContext = Depends(get_request_context),
) -> list[SettingsUser]:
    if not AccessPolicy(db, context).is_admin():
        raise access_denied()
    return SettingsSnapshotService(db).load(context).users
