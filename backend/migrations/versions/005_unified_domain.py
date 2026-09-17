"""Unify account-scoped identities, membership history and activity semantics.

Revision ID: 005
Revises: 004

Legacy work_sessions.user_id is an EXTERNAL amoCRM user ID. Its account is
resolved using 004's globally unique users.amocrm_user_id. Unmapped rows abort
the transaction; no synthetic user/account or confirmed duration is invented.
"""

from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def reject_if(sql, message):
    if op.get_bind().execute(sa.text(sql)).first():
        raise RuntimeError(message)


def upgrade():
    op.create_check_constraint(
        "ck_work_sessions_status",
        "work_sessions",
        "current_status IN ('working','break','finished')",
    )
    op.create_check_constraint(
        "ck_status_transitions_status",
        "status_transitions",
        "to_status IN ('working','break','finished') AND (from_status IS NULL OR from_status IN ('working','break','finished'))",
    )
    reject_if(
        "SELECT 1 FROM work_sessions w LEFT JOIN users u ON u.amocrm_user_id=w.user_id WHERE u.id IS NULL LIMIT 1",
        "005: unmapped legacy work_sessions; reconcile external user identities before retrying",
    )
    op.add_column(
        "departments",
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
    )
    op.create_foreign_key(
        "fk_users_department", "users", "departments", ["department_id"], ["id"]
    )
    op.drop_constraint("users_amocrm_user_id_key", "users", type_="unique")
    op.drop_index("ix_users_amocrm_user_id", table_name="users")
    op.create_index("ix_users_amocrm_user_id", "users", ["amocrm_user_id"])
    op.create_unique_constraint(
        "uq_users_account_amocrm_user", "users", ["amocrm_account_id", "amocrm_user_id"]
    )
    op.create_unique_constraint(
        "uq_users_account_internal_id", "users", ["amocrm_account_id", "id"]
    )

    op.alter_column("work_sessions", "user_id", new_column_name="amocrm_user_id")
    op.execute(
        "ALTER INDEX ix_work_sessions_user_id RENAME TO ix_work_sessions_amocrm_user_id"
    )
    op.add_column(
        "work_sessions", sa.Column("amocrm_account_id", sa.Integer(), nullable=True)
    )
    op.execute(
        "UPDATE work_sessions w SET amocrm_account_id=u.amocrm_account_id FROM users u WHERE w.amocrm_user_id=u.amocrm_user_id"
    )
    op.alter_column("work_sessions", "amocrm_account_id", nullable=False)
    op.create_index(
        "ix_work_sessions_amocrm_account_id", "work_sessions", ["amocrm_account_id"]
    )
    op.create_foreign_key(
        "fk_work_sessions_amocrm_identity",
        "work_sessions",
        "users",
        ["amocrm_account_id", "amocrm_user_id"],
        ["amocrm_account_id", "amocrm_user_id"],
    )
    for name in (
        "active_duration",
        "unconfirmed_duration",
        "break_duration",
        "idle_duration",
    ):
        op.add_column(
            "work_sessions",
            sa.Column(name, sa.Integer(), nullable=False, server_default="0"),
        )
    op.execute(
        "UPDATE work_sessions SET unconfirmed_duration=total_work_time, break_duration=total_break_time"
    )
    op.create_check_constraint(
        "ck_work_sessions_durations",
        "work_sessions",
        "active_duration >= 0 AND unconfirmed_duration >= 0 AND break_duration >= 0 AND idle_duration >= 0",
    )

    op.create_unique_constraint(
        "uq_widget_groups_account_id", "widget_groups", ["account_id", "id"]
    )
    op.drop_constraint(
        "widget_groups_manager_user_id_fkey", "widget_groups", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_widget_groups_account_manager",
        "widget_groups",
        "users",
        ["account_id", "manager_user_id"],
        ["amocrm_account_id", "id"],
    )
    op.add_column(
        "group_members",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.drop_constraint("uq_group_members_account_user", "group_members", type_="unique")
    op.create_index(
        "uq_group_members_active_account_user",
        "group_members",
        ["account_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("is_active"),
    )
    op.drop_constraint(
        "group_members_group_id_fkey", "group_members", type_="foreignkey"
    )
    op.drop_constraint(
        "group_members_user_id_fkey", "group_members", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_group_members_account_user",
        "group_members",
        "users",
        ["account_id", "user_id"],
        ["amocrm_account_id", "id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "fk_group_members_account_group",
        "group_members",
        "widget_groups",
        ["account_id", "group_id"],
        ["account_id", "id"],
        ondelete="CASCADE",
    )

    op.alter_column("crm_events", "source_event_id", new_column_name="external_id")
    op.drop_constraint("uq_crm_events_source_id", "crm_events", type_="unique")
    op.create_unique_constraint(
        "uq_crm_events_external_id", "crm_events", ["account_id", "external_id"]
    )
    for table in ("crm_events", "call_events"):
        op.alter_column(
            table, "user_id", new_column_name="author_amocrm_user_id", nullable=True
        )
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.add_column(table, sa.Column("user_id", sa.Integer(), nullable=True))
        op.execute(
            f"UPDATE {table} e SET user_id=u.id FROM users u WHERE e.account_id=u.amocrm_account_id AND e.author_amocrm_user_id=u.amocrm_user_id AND e.author_amocrm_user_id > 0"
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
        op.create_foreign_key(
            f"fk_{table}_account_user",
            table,
            "users",
            ["account_id", "user_id"],
            ["amocrm_account_id", "id"],
        )
        op.create_check_constraint(
            f"ck_{table}_author",
            table,
            "user_id IS NULL OR (author_amocrm_user_id IS NOT NULL AND author_amocrm_user_id > 0)",
        )
    op.execute("UPDATE crm_events SET is_complete=0 WHERE user_id IS NULL")
    op.alter_column("crm_events", "is_complete", server_default="0")
    op.create_check_constraint(
        "ck_crm_events_attribution",
        "crm_events",
        "is_complete IN (0,1) AND (is_complete = 0 OR user_id IS NOT NULL)",
    )
    op.alter_column("call_events", "direction", nullable=True)
    op.create_check_constraint(
        "ck_call_events_duration",
        "call_events",
        "duration_seconds IS NULL OR duration_seconds >= 0",
    )

    # Legacy browser labels are explicitly neutral. Unknown sources abort via
    # the constraint rather than silently being turned into confirmed work.
    op.execute(
        "UPDATE activity_intervals SET source='unconfirmed_input',kind='unconfirmed' WHERE source='browser_input'"
    )
    op.create_check_constraint(
        "ck_activity_intervals_time", "activity_intervals", "ended_at >= started_at"
    )
    op.create_check_constraint(
        "ck_activity_intervals_source",
        "activity_intervals",
        "source IN ('crm_event','call','unconfirmed_input')",
    )
    op.create_check_constraint(
        "ck_activity_intervals_kind",
        "activity_intervals",
        "(source = 'unconfirmed_input' AND kind = 'unconfirmed') OR (source IN ('crm_event','call') AND kind = 'confirmed' AND work_session_id IS NOT NULL)",
    )
    op.drop_constraint(
        "activity_intervals_user_id_fkey", "activity_intervals", type_="foreignkey"
    )
    op.create_foreign_key(
        "fk_activity_intervals_account_user",
        "activity_intervals",
        "users",
        ["account_id", "user_id"],
        ["amocrm_account_id", "id"],
        ondelete="CASCADE",
    )

    # These indexes already exist in ORM metadata but were omitted in history.
    for table in (
        "work_sessions",
        "widget_groups",
        "group_members",
        "crm_events",
        "call_events",
        "activity_intervals",
    ):
        op.create_index(f"ix_{table}_id", table, ["id"])
    op.create_index("ix_crm_events_event_type", "crm_events", ["event_type"])
    op.create_index(
        "ix_call_events_source_event_id", "call_events", ["source_event_id"]
    )
    op.create_index(
        "ix_activity_intervals_ended_at", "activity_intervals", ["ended_at"]
    )


def downgrade():
    # 004 cannot represent these states. Refuse instead of deleting history,
    # assigning a fake author, or silently merging accounts.
    reject_if(
        "SELECT 1 FROM users GROUP BY amocrm_user_id HAVING count(*)>1",
        "004 cannot represent repeated external user IDs across accounts",
    )
    reject_if(
        "SELECT 1 FROM group_members GROUP BY account_id,user_id HAVING count(*)>1",
        "004 cannot represent membership history",
    )
    reject_if(
        "SELECT 1 FROM group_members WHERE NOT is_active",
        "004 cannot represent inactive membership",
    )
    reject_if(
        "SELECT 1 FROM departments WHERE timezone <> 'UTC'",
        "004 cannot represent department timezones",
    )
    reject_if(
        "SELECT 1 FROM work_sessions WHERE unconfirmed_duration<>total_work_time OR break_duration<>total_break_time",
        "004 cannot represent independent duration counters",
    )
    for table in ("crm_events", "call_events"):
        reject_if(
            f"SELECT 1 FROM {table} WHERE author_amocrm_user_id IS NULL",
            "004 cannot represent unattributed events without a raw legacy author",
        )
    reject_if(
        "SELECT 1 FROM call_events WHERE direction IS NULL",
        "004 cannot represent unknown call direction",
    )
    reject_if(
        "SELECT 1 FROM work_sessions WHERE active_duration<>0 OR idle_duration<>0",
        "004 cannot represent measured activity/idle durations",
    )
    for table in (
        "work_sessions",
        "widget_groups",
        "group_members",
        "crm_events",
        "call_events",
        "activity_intervals",
    ):
        op.drop_index(f"ix_{table}_id", table_name=table)
    op.drop_index("ix_crm_events_event_type", table_name="crm_events")
    op.drop_index("ix_call_events_source_event_id", table_name="call_events")
    op.drop_index("ix_activity_intervals_ended_at", table_name="activity_intervals")
    op.drop_constraint(
        "fk_activity_intervals_account_user", "activity_intervals", type_="foreignkey"
    )
    op.create_foreign_key(
        "activity_intervals_user_id_fkey",
        "activity_intervals",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    for name in ("time", "source", "kind"):
        op.drop_constraint(
            f"ck_activity_intervals_{name}", "activity_intervals", type_="check"
        )
    op.drop_constraint("ck_call_events_duration", "call_events", type_="check")
    op.alter_column("call_events", "direction", nullable=False)
    op.drop_constraint("ck_crm_events_attribution", "crm_events", type_="check")
    op.alter_column("crm_events", "is_complete", server_default="1")
    for table in ("crm_events", "call_events"):
        op.drop_constraint(f"ck_{table}_author", table, type_="check")
        op.drop_constraint(f"fk_{table}_account_user", table, type_="foreignkey")
        op.drop_index(f"ix_{table}_user_id", table_name=table)
        op.drop_column(table, "user_id")
        op.alter_column(
            table, "author_amocrm_user_id", new_column_name="user_id", nullable=False
        )
        op.create_index(f"ix_{table}_user_id", table, ["user_id"])
    op.drop_constraint("uq_crm_events_external_id", "crm_events", type_="unique")
    op.alter_column("crm_events", "external_id", new_column_name="source_event_id")
    op.create_unique_constraint(
        "uq_crm_events_source_id", "crm_events", ["account_id", "source_event_id"]
    )
    op.drop_constraint(
        "fk_group_members_account_user", "group_members", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_group_members_account_group", "group_members", type_="foreignkey"
    )
    op.create_foreign_key(
        "group_members_user_id_fkey",
        "group_members",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_foreign_key(
        "group_members_group_id_fkey",
        "group_members",
        "widget_groups",
        ["group_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_index("uq_group_members_active_account_user", table_name="group_members")
    op.create_unique_constraint(
        "uq_group_members_account_user", "group_members", ["account_id", "user_id"]
    )
    op.drop_column("group_members", "is_active")
    op.drop_constraint(
        "fk_widget_groups_account_manager", "widget_groups", type_="foreignkey"
    )
    op.create_foreign_key(
        "widget_groups_manager_user_id_fkey",
        "widget_groups",
        "users",
        ["manager_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.drop_constraint("uq_widget_groups_account_id", "widget_groups", type_="unique")
    op.drop_constraint("ck_work_sessions_durations", "work_sessions", type_="check")
    for name in (
        "active_duration",
        "unconfirmed_duration",
        "break_duration",
        "idle_duration",
    ):
        op.drop_column("work_sessions", name)
    op.drop_constraint(
        "fk_work_sessions_amocrm_identity", "work_sessions", type_="foreignkey"
    )
    op.drop_index("ix_work_sessions_amocrm_account_id", table_name="work_sessions")
    op.drop_column("work_sessions", "amocrm_account_id")
    op.alter_column("work_sessions", "amocrm_user_id", new_column_name="user_id")
    op.execute(
        "ALTER INDEX ix_work_sessions_amocrm_user_id RENAME TO ix_work_sessions_user_id"
    )
    op.drop_constraint("uq_users_account_amocrm_user", "users", type_="unique")
    op.drop_constraint("uq_users_account_internal_id", "users", type_="unique")
    op.drop_index("ix_users_amocrm_user_id", table_name="users")
    op.create_index("ix_users_amocrm_user_id", "users", ["amocrm_user_id"], unique=True)
    op.create_unique_constraint("users_amocrm_user_id_key", "users", ["amocrm_user_id"])
    op.drop_constraint("fk_users_department", "users", type_="foreignkey")
    op.drop_column("departments", "timezone")
    op.drop_constraint("ck_work_sessions_status", "work_sessions", type_="check")
    op.drop_constraint(
        "ck_status_transitions_status", "status_transitions", type_="check"
    )
