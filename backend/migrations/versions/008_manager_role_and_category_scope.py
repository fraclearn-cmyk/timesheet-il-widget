"""Bind manager assignments to observed role snapshots and scope category names."""

from alembic import op
import sqlalchemy as sa


revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def _reject_if(sql: str, message: str) -> None:
    if op.get_bind().execute(sa.text(sql)).first():
        raise RuntimeError(message)


def upgrade() -> None:
    op.add_column(
        "widget_groups", sa.Column("manager_role_id", sa.Integer(), nullable=True)
    )
    op.execute(
        sa.text(
            """
            UPDATE widget_groups g
            SET manager_role_id = u.amocrm_role_id
            FROM users u
            WHERE g.account_id = u.amocrm_account_id
              AND g.manager_user_id = u.id
              AND u.amocrm_role_id IS NOT NULL
            """
        )
    )
    op.drop_constraint(
        "activity_categories_name_key", "activity_categories", type_="unique"
    )
    op.create_unique_constraint(
        "uq_activity_categories_account_name",
        "activity_categories",
        ["account_id", "name"],
    )


def downgrade() -> None:
    _reject_if(
        "SELECT 1 FROM widget_groups WHERE manager_role_id IS NOT NULL LIMIT 1",
        "008 downgrade would erase trusted manager role snapshots",
    )
    _reject_if(
        "SELECT 1 FROM activity_categories GROUP BY name HAVING count(*) > 1 LIMIT 1",
        "008 downgrade cannot represent duplicate category names across accounts",
    )
    op.drop_constraint(
        "uq_activity_categories_account_name", "activity_categories", type_="unique"
    )
    op.create_unique_constraint(
        "activity_categories_name_key", "activity_categories", ["name"]
    )
    op.drop_column("widget_groups", "manager_role_id")
