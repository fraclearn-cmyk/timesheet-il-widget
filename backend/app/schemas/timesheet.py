"""Public status contract for the authenticated employee widget."""

from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID


class TimesheetStatusResponse(BaseModel):
    session_id: int | None
    status: str
    started_at: str | None
    ended_at: str | None
    break_seconds: int
    track_time: bool
    hide_widget: bool
    restart_allowed: bool

    @field_validator("started_at", "ended_at")
    @classmethod
    def utc_z(cls, value: str | None) -> str | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class TimesheetCommandResponse(TimesheetStatusResponse):
    message: str
