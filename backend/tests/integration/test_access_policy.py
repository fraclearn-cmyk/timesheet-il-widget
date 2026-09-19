from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import pytest

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
        id=1,
        amocrm_user_id=11,
        amocrm_account_id=1,
        name="Manager",
        role=UserRole.EMPLOYEE,
        amocrm_role_id=77,
        amocrm_rights={"role_id": 77, "is_admin": False},
    )
    own_member = User(id=2, amocrm_user_id=12, amocrm_account_id=1, name="Own")
    foreign_manager = User(
        id=3,
        amocrm_user_id=13,
        amocrm_account_id=1,
        name="Foreign manager",
        role=UserRole.EMPLOYEE,
        amocrm_role_id=88,
        amocrm_rights={"role_id": 88, "is_admin": False},
    )
    foreign_member = User(id=4, amocrm_user_id=14, amocrm_account_id=1, name="Foreign")
    first = WidgetGroup(
        id=10, account_id=1, name="First", manager_user_id=1, manager_role_id=77
    )
    second = WidgetGroup(
        id=20, account_id=1, name="Second", manager_user_id=3, manager_role_id=88
    )
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


def test_manager_role_snapshot_must_match_live_role_and_assignment():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        id=1,
        amocrm_user_id=11,
        amocrm_account_id=1,
        name="Manager",
        role=UserRole.ROP,
        amocrm_role_id=77,
        amocrm_rights={"role_id": 77, "is_admin": False},
    )
    member = User(id=2, amocrm_user_id=12, amocrm_account_id=1, name="Member")
    group = WidgetGroup(
        id=10, account_id=1, name="First", manager_user_id=1, manager_role_id=77
    )
    db.add_all(
        [manager, member, group, GroupMember(account_id=1, group_id=10, user_id=2)]
    )
    db.commit()

    policy = AccessPolicy(db, RequestContext(account_id=1, user=manager))
    assert policy.can_view_user(member) is True

    manager.amocrm_role_id = 78
    assert policy.can_view_user(member) is False
    manager.amocrm_role_id = None
    assert policy.can_view_user(member) is False


def test_local_rop_without_snapshot_is_not_manager_authority():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    manager = User(
        id=1, amocrm_user_id=11, amocrm_account_id=1, name="Manager", role=UserRole.ROP
    )
    member = User(id=2, amocrm_user_id=12, amocrm_account_id=1, name="Member")
    group = WidgetGroup(id=10, account_id=1, name="First", manager_user_id=1)
    db.add_all(
        [manager, member, group, GroupMember(account_id=1, group_id=10, user_id=2)]
    )
    db.commit()

    assert (
        AccessPolicy(db, RequestContext(account_id=1, user=manager)).can_view_user(
            member
        )
        is False
    )


def test_manager_live_role_only_grants_members_of_matching_group_snapshot():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        manager = User(
            id=1,
            amocrm_user_id=11,
            amocrm_account_id=1,
            name="Manager",
            amocrm_role_id=78,
            amocrm_rights={"role_id": 78, "is_admin": False},
        )
        stale_member = User(id=2, amocrm_user_id=12, amocrm_account_id=1, name="Stale")
        live_member = User(id=3, amocrm_user_id=13, amocrm_account_id=1, name="Live")
        db.add_all(
            [
                manager,
                stale_member,
                live_member,
                WidgetGroup(
                    id=10,
                    account_id=1,
                    name="Stale",
                    manager_user_id=1,
                    manager_role_id=77,
                ),
                WidgetGroup(
                    id=20,
                    account_id=1,
                    name="Live",
                    manager_user_id=1,
                    manager_role_id=78,
                ),
                GroupMember(account_id=1, group_id=10, user_id=2),
                GroupMember(account_id=1, group_id=20, user_id=3),
            ]
        )
        db.commit()
        policy = AccessPolicy(db, RequestContext(account_id=1, user=manager))
        assert policy.is_manager()
        assert policy.can_view_user(live_member)
        assert not policy.can_view_user(stale_member)
        assert policy.visible_internal_user_ids() == {1, 3}
        assert policy.visible_external_user_ids() == {11, 13}


def test_manager_assignment_captures_observed_snapshot_and_checks_account():
    manager = User(
        id=1,
        amocrm_user_id=11,
        amocrm_account_id=1,
        name="Manager",
        amocrm_role_id=77,
    )
    group = WidgetGroup(id=10, account_id=1, name="First")
    group.assign_manager(manager)
    assert group.manager_user_id == 1
    assert group.manager_role_id == 77

    manager.amocrm_account_id = 2
    with pytest.raises(ValueError, match="another account"):
        group.assign_manager(manager)


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
