from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.access_policy import AccessPolicy, RequestContext
from app.core.database import Base
from app.models.group_member import GroupMember
from app.models.user import User, UserRole
from app.models.widget_group import WidgetGroup


def test_manager_cannot_see_a_member_of_another_group():
    """Dropping the group predicate would leak the foreign employee to a manager."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        id=1, amocrm_user_id=11, amocrm_account_id=1, name="Manager", role=UserRole.ROP
    )
    own_member = User(id=2, amocrm_user_id=12, amocrm_account_id=1, name="Own")
    foreign_manager = User(
        id=3,
        amocrm_user_id=13,
        amocrm_account_id=1,
        name="Foreign manager",
        role=UserRole.ROP,
    )
    foreign_member = User(id=4, amocrm_user_id=14, amocrm_account_id=1, name="Foreign")
    first = WidgetGroup(id=10, account_id=1, name="First", manager_user_id=1)
    second = WidgetGroup(id=20, account_id=1, name="Second", manager_user_id=3)
    db.add_all([manager, own_member, foreign_manager, foreign_member, first, second])
    db.add_all(
        [
            GroupMember(account_id=1, group_id=10, user_id=2, is_active=True),
            GroupMember(account_id=1, group_id=20, user_id=4, is_active=True),
        ]
    )
    db.commit()

    policy = AccessPolicy(db, RequestContext(account_id=1, user=manager))

    assert policy.can_view_user(own_member) is True
    assert policy.can_view_user(foreign_member) is False


def test_admin_does_not_cross_account_boundary():
    """Removing account scope would allow an administrator to read another tenant."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    admin = User(
        id=1, amocrm_user_id=11, amocrm_account_id=1, name="Admin", role=UserRole.ADMIN
    )
    foreign = User(id=2, amocrm_user_id=11, amocrm_account_id=2, name="Foreign")
    db.add_all([admin, foreign])
    db.commit()

    assert (
        AccessPolicy(db, RequestContext(account_id=1, user=admin)).can_view_user(
            foreign
        )
        is False
    )
