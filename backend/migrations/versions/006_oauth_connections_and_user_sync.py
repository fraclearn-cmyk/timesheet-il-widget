"""Add encrypted OAuth connections and observed amoCRM user metadata.

Revision ID: 006
Revises: 005
"""

from alembic import op
import sqlalchemy as sa


revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "oauth_connections",
        sa.Column("account_id", sa.Integer(), primary_key=True),
        sa.Column("account_url", sa.String(length=255), nullable=False),
        sa.Column("account_name", sa.String(length=255), nullable=True),
        sa.Column("encrypted_access_token", sa.Text(), nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text(), nullable=False),
        sa.Column("access_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.add_column(
        "users", sa.Column("avatar_url", sa.String(length=2048), nullable=True)
    )
    op.add_column("users", sa.Column("amocrm_rights", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("amocrm_role_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "amocrm_role_id")
    op.drop_column("users", "amocrm_rights")
    op.drop_column("users", "avatar_url")
    op.drop_table("oauth_connections")
