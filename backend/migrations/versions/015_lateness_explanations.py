"""Store separate late starts and break returns with account-scoped identities.

Revision ID: 015
Revises: 014
"""

from alembic import op
import sqlalchemy as sa


revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("group_members", sa.Column("require_late_reason", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("widget_groups", sa.Column("break_limit_minutes", sa.Integer(), nullable=False, server_default="60"))
    op.create_check_constraint("ck_widget_groups_break_limit_minutes", "widget_groups", "break_limit_minutes BETWEEN 1 AND 720")
    op.alter_column("work_sessions", "late_reason", existing_type=sa.String(500), type_=sa.String(1000), existing_nullable=True)
    op.add_column("timesheet_commands", sa.Column("request_hash", sa.String(64), nullable=True))
    # Tie the incident to the actual owner of its session, not merely any user
    # in the same account.
    op.create_unique_constraint("uq_work_sessions_account_user_id", "work_sessions", ["amocrm_account_id", "amocrm_user_id", "id"])
    op.create_table(
        "lateness_incidents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("work_session_id", sa.Integer(), nullable=False),
        sa.Column("amocrm_user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=False),
        sa.Column("late_minutes", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("work_session_id", "kind", "sequence", name="uq_lateness_incidents_session_kind_sequence"),
        sa.ForeignKeyConstraint(["account_id", "amocrm_user_id"], ["users.amocrm_account_id", "users.amocrm_user_id"], name="fk_lateness_incidents_account_user"),
        sa.ForeignKeyConstraint(["account_id", "amocrm_user_id", "work_session_id"], ["work_sessions.amocrm_account_id", "work_sessions.amocrm_user_id", "work_sessions.id"], name="fk_lateness_incidents_account_user_session", ondelete="CASCADE"),
        sa.CheckConstraint("late_minutes > 0", name="ck_lateness_incidents_positive_minutes"),
        sa.CheckConstraint("(kind = 'shift_start' AND sequence = 0) OR (kind = 'break_return' AND sequence > 0)", name="ck_lateness_incidents_kind_sequence"),
        sa.CheckConstraint("reason IS NULL OR length(reason) <= 1000", name="ck_lateness_incidents_reason_length"),
    )
    op.create_index("ix_lateness_incidents_account_user_occurred_at", "lateness_incidents", ["account_id", "amocrm_user_id", "occurred_at"])
    op.create_index("ix_lateness_incidents_account_session", "lateness_incidents", ["account_id", "work_session_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(sa.text("""
        SELECT EXISTS (SELECT 1 FROM lateness_incidents)
            OR EXISTS (SELECT 1 FROM group_members WHERE require_late_reason)
            OR EXISTS (SELECT 1 FROM widget_groups WHERE break_limit_minutes <> 60)
            OR EXISTS (SELECT 1 FROM timesheet_commands WHERE request_hash IS NOT NULL)
            OR EXISTS (SELECT 1 FROM work_sessions WHERE length(late_reason) > 500)
    """)):
        raise RuntimeError("cannot downgrade recorded lateness explanation data")
    op.drop_index("ix_lateness_incidents_account_session", table_name="lateness_incidents")
    op.drop_index("ix_lateness_incidents_account_user_occurred_at", table_name="lateness_incidents")
    op.drop_table("lateness_incidents")
    op.drop_constraint("uq_work_sessions_account_user_id", "work_sessions", type_="unique")
    op.drop_column("timesheet_commands", "request_hash")
    op.alter_column("work_sessions", "late_reason", existing_type=sa.String(1000), type_=sa.String(500), existing_nullable=True)
    op.drop_constraint("ck_widget_groups_break_limit_minutes", "widget_groups", type_="check")
    op.drop_column("widget_groups", "break_limit_minutes")
    op.drop_column("group_members", "require_late_reason")
