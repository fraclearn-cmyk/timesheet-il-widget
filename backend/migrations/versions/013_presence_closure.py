"""Track one-time closure of neutral presence intervals.

Revision ID: 013
Revises: 012
"""

from alembic import op
import sqlalchemy as sa


revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "activity_intervals", sa.Column("closed_at", sa.DateTime(), nullable=True)
    )
    op.create_index(
        "ix_activity_intervals_open_presence_end",
        "activity_intervals",
        ["ended_at", "user_id"],
        postgresql_where=sa.text("source = 'unconfirmed_input' AND closed_at IS NULL"),
    )


def downgrade() -> None:
    if op.get_bind().scalar(
        sa.text("SELECT count(*) FROM activity_intervals WHERE closed_at IS NOT NULL")
    ):
        raise RuntimeError("cannot downgrade recorded presence closure data")
    op.drop_index(
        "ix_activity_intervals_open_presence_end", table_name="activity_intervals"
    )
    op.drop_column("activity_intervals", "closed_at")
