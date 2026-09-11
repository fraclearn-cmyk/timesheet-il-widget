"""add widget groups and normalized activity tables

Revision ID: 004
Revises: e1db632ded80
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "e1db632ded80"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "widget_groups",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("work_start_time", sa.Time(), nullable=False),
        sa.Column("work_end_time", sa.Time(), nullable=False),
        sa.Column("manager_user_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["manager_user_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_widget_groups_account_id", "widget_groups", ["account_id"])

    op.create_table(
        "group_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("group_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("track_time", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("hide_widget", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["widget_groups.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("account_id", "user_id", name="uq_group_members_account_user"),
    )
    op.create_index("ix_group_members_account_id", "group_members", ["account_id"])

    op.create_table(
        "crm_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("object_type", sa.String(50), nullable=True),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("card_url", sa.String(1000), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("is_complete", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "source_event_id", name="uq_crm_events_source_id"),
    )
    op.create_index("ix_crm_events_account_id", "crm_events", ["account_id"])
    op.create_index("ix_crm_events_user_id", "crm_events", ["user_id"])
    op.create_index("ix_crm_events_occurred_at", "crm_events", ["occurred_at"])

    op.create_table(
        "call_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.String(255), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("object_type", sa.String(50), nullable=True),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("card_url", sa.String(1000), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_call_events_account_id", "call_events", ["account_id"])
    op.create_index("ix_call_events_user_id", "call_events", ["user_id"])
    op.create_index("ix_call_events_occurred_at", "call_events", ["occurred_at"])

    op.create_table(
        "activity_intervals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("work_session_id", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("ended_at", sa.DateTime(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("duration_source", sa.String(30), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=True),
        sa.Column("object_type", sa.String(50), nullable=True),
        sa.Column("object_id", sa.Integer(), nullable=True),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["work_session_id"], ["work_sessions.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_activity_intervals_account_id", "activity_intervals", ["account_id"])
    op.create_index("ix_activity_intervals_user_id", "activity_intervals", ["user_id"])
    op.create_index("ix_activity_intervals_started_at", "activity_intervals", ["started_at"])


def downgrade() -> None:
    op.drop_index("ix_activity_intervals_started_at", table_name="activity_intervals")
    op.drop_index("ix_activity_intervals_user_id", table_name="activity_intervals")
    op.drop_index("ix_activity_intervals_account_id", table_name="activity_intervals")
    op.drop_table("activity_intervals")
    op.drop_index("ix_call_events_occurred_at", table_name="call_events")
    op.drop_index("ix_call_events_user_id", table_name="call_events")
    op.drop_index("ix_call_events_account_id", table_name="call_events")
    op.drop_table("call_events")
    op.drop_index("ix_crm_events_occurred_at", table_name="crm_events")
    op.drop_index("ix_crm_events_user_id", table_name="crm_events")
    op.drop_index("ix_crm_events_account_id", table_name="crm_events")
    op.drop_table("crm_events")
    op.drop_index("ix_group_members_account_id", table_name="group_members")
    op.drop_table("group_members")
    op.drop_index("ix_widget_groups_account_id", table_name="widget_groups")
    op.drop_table("widget_groups")