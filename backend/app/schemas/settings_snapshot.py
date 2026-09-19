"""Public read contracts for the account-scoped settings snapshot."""

from datetime import time

from pydantic import BaseModel, ConfigDict, Field


class _StrictResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AccountSettings(_StrictResponseModel):
    support_phone: str | None
    allowed_statuses: list[str]
    default_allow_restart_session: bool


class SettingsGroup(_StrictResponseModel):
    id: int = Field(gt=0)
    account_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    timezone: str = Field(min_length=1)
    work_start_time: time
    work_end_time: time
    manager_amocrm_user_id: int | None = Field(default=None, gt=0)
    is_active: bool
    allow_restart_session: bool


class SettingsUser(_StrictResponseModel):
    amocrm_user_id: int = Field(gt=0)
    name: str = Field(min_length=1)
    email: str | None
    avatar_url: str | None
    amocrm_group_id: int | None = Field(default=None, gt=0)
    amocrm_group_label: str
    is_active: bool
    track_time: bool
    hide_widget: bool
    group_id: int | None = Field(default=None, gt=0)


class SettingsSnapshotResponse(_StrictResponseModel):
    revision: int = Field(ge=1)
    settings: AccountSettings
    groups: list[SettingsGroup]
    users: list[SettingsUser]
