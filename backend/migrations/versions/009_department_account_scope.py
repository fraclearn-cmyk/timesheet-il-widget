"""Give departments explicit account ownership and account-scoped names."""

from alembic import op
import sqlalchemy as sa


revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def _reject_if(sql: str, message: str) -> None:
    if op.get_bind().execute(sa.text(sql)).first():
        raise RuntimeError(message)


def upgrade() -> None:
    op.add_column("departments", sa.Column("account_id", sa.Integer(), nullable=True))
    op.create_index(
        "ix_departments_account_id", "departments", ["account_id"], unique=False
    )
    op.execute(
        sa.text(
            """
            UPDATE departments d
            SET account_id = owners.amocrm_account_id
            FROM (
                SELECT department_id, min(amocrm_account_id) AS amocrm_account_id
                FROM users
                WHERE department_id IS NOT NULL
                GROUP BY department_id
                HAVING count(DISTINCT amocrm_account_id) = 1
            ) owners
            WHERE d.id = owners.department_id
            """
        )
    )
    op.drop_constraint("departments_name_key", "departments", type_="unique")
    op.create_unique_constraint(
        "uq_departments_account_name", "departments", ["account_id", "name"]
    )


def downgrade() -> None:
    _reject_if(
        """
        SELECT 1
        FROM departments d
        WHERE d.account_id IS NOT NULL
          AND (
            NOT EXISTS (
                SELECT 1 FROM users u
                WHERE u.department_id = d.id
                  AND u.amocrm_account_id = d.account_id
            )
            OR EXISTS (
                SELECT 1 FROM users u
                WHERE u.department_id = d.id
                  AND u.amocrm_account_id <> d.account_id
            )
          )
        LIMIT 1
        """,
        "009 downgrade would erase explicit department account ownership",
    )
    _reject_if(
        "SELECT 1 FROM departments GROUP BY name HAVING count(*) > 1 LIMIT 1",
        "009 downgrade cannot represent duplicate department names across accounts",
    )
    op.drop_constraint("uq_departments_account_name", "departments", type_="unique")
    op.create_unique_constraint("departments_name_key", "departments", ["name"])
    op.drop_index("ix_departments_account_id", table_name="departments")
    op.drop_column("departments", "account_id")
