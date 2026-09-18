"""Add an explicit account owner to activity categories.

Legacy categories are backfilled only when every historical event proves the
same account.  Ambiguous or unreferenced rows remain NULL and are fail-closed
by the API until an operator assigns an owner explicitly.
"""

from alembic import op
import sqlalchemy as sa


revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activity_categories", sa.Column("account_id", sa.Integer(), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE activity_categories
            SET account_id = (
                SELECT MIN(ws.amocrm_account_id)
                FROM activity_events ae
                JOIN activity_sessions ass ON ass.id = ae.activity_session_id
                JOIN work_sessions ws ON ws.id = ass.work_session_id
                WHERE ae.category_id = activity_categories.id
            )
            WHERE id IN (
                SELECT ae.category_id
                FROM activity_events ae
                JOIN activity_sessions ass ON ass.id = ae.activity_session_id
                JOIN work_sessions ws ON ws.id = ass.work_session_id
                WHERE ae.category_id IS NOT NULL
                GROUP BY ae.category_id
                HAVING COUNT(DISTINCT ws.amocrm_account_id) = 1
            )
            """
        )
    )
    op.create_index(
        "ix_activity_categories_account_id",
        "activity_categories",
        ["account_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_activity_categories_account_id", table_name="activity_categories")
    op.drop_column("activity_categories", "account_id")
