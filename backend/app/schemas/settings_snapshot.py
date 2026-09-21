"""Public contracts for the account-scoped settings snapshot."""

from datetime import time
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StringConstraints


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


PositiveId = Annotated[int, Field(strict=True, gt=0)]
ClientKey = Annotated[
    str, StringConstraints(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
]


class AccountSettingsUpdate(_StrictResponseModel):
    support_phone: str | None = Field(max_length=64)
    allowed_statuses: list[Literal["working", "break", "finished"]] = Field(
        min_length=1, max_length=3
    )
    default_allow_restart_session: StrictBool


class SettingsGroupUpdate(_StrictResponseModel):
    id: PositiveId | None = None
    client_key: ClientKey | None = None
    name: str = Field(min_length=1, max_length=255)
    timezone: str = Field(min_length=1, max_length=64)
    work_start_time: time
    work_end_time: time
    manager_amocrm_user_id: PositiveId | None = None
    is_active: StrictBool
    allow_restart_session: StrictBool

    @property
    def reference(self) -> str:
        return f"id:{self.id}" if self.id is not None else f"client:{self.client_key}"


class SettingsUserUpdate(_StrictResponseModel):
    amocrm_user_id: PositiveId
    track_time: StrictBool
    hide_widget: StrictBool
    group_ref: str | None = Field(
        max_length=71, pattern=r"^(id:[1-9][0-9]*|client:[A-Za-z0-9_-]{1,64})$"
    )


class SettingsSnapshotUpdate(_StrictResponseModel):
    revision: PositiveId
    settings: AccountSettingsUpdate
    groups: list[SettingsGroupUpdate]
    users: list[SettingsUserUpdate]
