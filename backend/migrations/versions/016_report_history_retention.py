"""Add manager timesheet report history limits.

Revision ID: 016
Revises: 015
"""

from alembic import op
import sqlalchemy as sa


revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "widget_groups",
        sa.Column(
            "report_history_days", sa.Integer(), nullable=False, server_default="365"
        ),
    )
    op.create_check_constraint(
        "ck_widget_groups_report_history_days",
        "widget_groups",
        "report_history_days BETWEEN 1 AND 365",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.scalar(
        sa.text(
            "SELECT EXISTS (SELECT 1 FROM widget_groups WHERE report_history_days <> 365)"
        )
    ):
        raise RuntimeError("cannot downgrade configured report history limits")
    op.drop_constraint(
        "ck_widget_groups_report_history_days", "widget_groups", type_="check"
    )
    op.drop_column("widget_groups", "report_history_days")
