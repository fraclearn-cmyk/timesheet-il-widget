import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.group_member import GroupMember
from app.models.user import User
from app.models.widget_group import WidgetGroup
from app.services.user_sync_service import UserSyncService


class FakeAmoCRM:
    async def get_account(self):
        return {"id": 50, "name": "Test account", "current_user_id": 501}

    async def list_users(self):
        return [
            {
                "id": 501,
                "name": "Updated",
                "email": "updated@example.invalid",
                "rights": {"is_admin": True, "group_id": 71},
            }
        ]


def test_sync_updates_current_users_and_deactivates_missing_users_without_history_loss():
    """Deleting a missing amoCRM user or keeping it active must fail this contract."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    missing = User(id=1, amocrm_user_id=500, amocrm_account_id=50, name="Old")
    current = User(id=2, amocrm_user_id=501, amocrm_account_id=50, name="Before")
    group = WidgetGroup(id=10, account_id=50, name="Preserved")
    membership = GroupMember(account_id=50, group_id=10, user_id=1, is_active=True)
    db.add_all([missing, current, group, membership])
    db.commit()

    result = asyncio.run(UserSyncService(db, FakeAmoCRM()).synchronize())

    assert result.updated == 1
    assert db.get(User, 1).is_active is False
    assert db.get(GroupMember, membership.id).is_active is True
    assert db.get(User, 2).name == "Updated"
    assert db.get(User, 2).amocrm_group_id == 71


@pytest.mark.parametrize("group_id", [True, False, 0, -1, "71", 7.1, None])
def test_sync_discards_non_positive_or_non_integer_amocrm_group_ids(group_id):
    class InvalidGroupAmoCRM(FakeAmoCRM):
        async def list_users(self):
            return [
                {
                    "id": 501,
                    "name": "Updated",
                    "rights": {"group_id": group_id},
                }
            ]

    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        asyncio.run(UserSyncService(db, InvalidGroupAmoCRM()).synchronize())
        assert db.query(User).one().amocrm_group_id is None
    engine.dispose()
