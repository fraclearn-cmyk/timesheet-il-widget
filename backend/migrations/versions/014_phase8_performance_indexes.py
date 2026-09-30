"""Add evidence-backed indexes for monitoring and reports.

Revision ID: 014
Revises: 013
"""

from alembic import op


revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_work_sessions_account_user_business_date",
        "work_sessions",
        ["amocrm_account_id", "amocrm_user_id", "business_date"],
    )
    op.create_index(
        "ix_status_transitions_session_timestamp_id",
        "status_transitions",
        ["work_session_id", "timestamp", "id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_status_transitions_session_timestamp_id",
        table_name="status_transitions",
    )
    op.drop_index(
        "ix_work_sessions_account_user_business_date",
        table_name="work_sessions",
    )
