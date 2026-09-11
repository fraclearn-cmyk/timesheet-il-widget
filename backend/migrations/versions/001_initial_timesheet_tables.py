"""create base timesheet tables

Revision ID: 001
Revises:
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("user_name", sa.String(255), nullable=False),
        sa.Column("department", sa.String(255), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("current_status", sa.String(30), nullable=False, server_default="working"),
        sa.Column("total_work_time", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_break_time", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("break_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_work_sessions_user_id", "work_sessions", ["user_id"])

    op.create_table(
        "activity_categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("color", sa.String(50), nullable=False),
        sa.Column("icon", sa.String(50), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )

    op.create_table(
        "activity_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_session_id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("entity_name", sa.String(500), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=False),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_activity_time", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["work_session_id"], ["work_sessions.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "activity_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("activity_session_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("event_data", sa.JSON(), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["activity_session_id"], ["activity_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["category_id"], ["activity_categories.id"]),
    )

    op.create_table(
        "status_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("work_session_id", sa.Integer(), nullable=False),
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=True),
        sa.Column("reason", sa.String(255), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.ForeignKeyConstraint(["work_session_id"], ["work_sessions.id"], ondelete="CASCADE"),
    )

    op.create_table(
        "widget_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False, unique=True),
        sa.Column("account_name", sa.String(255), nullable=True),
        sa.Column("polling_interval", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("inactivity_timeout", sa.Integer(), nullable=False, server_default="300"),
        sa.Column("enable_activity_tracking", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enable_overlay_blocking", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("enable_auto_finish", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("excel_columns", sa.JSON(), nullable=True),
        sa.Column("settings", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("widget_settings")
    op.drop_table("status_transitions")
    op.drop_table("activity_events")
    op.drop_table("activity_sessions")
    op.drop_table("activity_categories")
    op.drop_index("ix_work_sessions_user_id", table_name="work_sessions")
    op.drop_table("work_sessions")