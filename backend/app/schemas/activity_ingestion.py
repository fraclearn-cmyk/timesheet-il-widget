"""Strict public schemas for privacy-preserving activity ingestion."""

from datetime import UTC, datetime

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    UUID4,
    field_serializer,
    field_validator,
)


class PresenceBatchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_id: UUID4
    window_started_at: datetime
    last_seen_at: datetime
    signal_count: int = Field(strict=True, ge=1, le=100_000)

    @field_validator("window_started_at", "last_seen_at")
    @classmethod
    def require_aware_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone")
        return value.astimezone(UTC)


class PresenceIntervalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    started_at: datetime
    ended_at: datetime
    kind: str
    source: str
    duration_source: str

    @field_serializer("started_at", "ended_at")
    def serialize_utc(self, value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
