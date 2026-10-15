"""Public status contract for the authenticated employee widget."""

from datetime import datetime, timezone
from uuid import UUID
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints, field_validator

from app.models.lateness_incident import LatenessKind


LatenessReason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class CommandRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    idempotency_key: UUID
    reason: LatenessReason | None = None

    @field_validator("reason", mode="before")
    @classmethod
    def empty_reason_is_absent(cls, value):
        return None if isinstance(value, str) and not value.strip() else value


class TimesheetStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: int | None
    status: str
    started_at: str | None
    ended_at: str | None
    break_seconds: int
    track_time: bool
    hide_widget: bool
    restart_allowed: bool
    late_reason_required: StrictBool = False
    late_reason_kind: LatenessKind | None = None
    late_minutes: int = Field(default=0, strict=True, ge=0)
    break_sequence: int | None = Field(default=None, strict=True, ge=1)

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
