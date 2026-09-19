"""Persist the phase 3 widget settings snapshot.

Revision ID: 010
Revises: 009
"""

from alembic import op
import sqlalchemy as sa


revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def _normalize_group_name(value: str) -> str:
    return value.strip().casefold()


def _backfill_group_name_keys() -> None:
    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, account_id, name FROM widget_groups ORDER BY id")
    ).mappings()
    seen: dict[tuple[int, str], int] = {}
    normalized: list[tuple[int, str]] = []
    for row in rows:
        name_key = _normalize_group_name(row["name"])
        scope = (row["account_id"], name_key)
        if scope in seen:
            raise RuntimeError(
                "010: normalized widget group names collide within account "
                f"{row['account_id']}: group IDs {seen[scope]} and {row['id']}"
            )
        seen[scope] = row["id"]
        normalized.append((row["id"], name_key))

    for group_id, name_key in normalized:
        connection.execute(
            sa.text("UPDATE widget_groups SET name_key=:name_key WHERE id=:id"),
            {"id": group_id, "name_key": name_key},
        )


def _reject_non_default_phase_3_values() -> None:
    connection = op.get_bind()
    if connection.execute(
        sa.text(
            """
            SELECT 1 FROM widget_settings
            WHERE support_phone IS NOT NULL
               OR allowed_statuses::jsonb <> '["working", "break", "finished"]'::jsonb
               OR default_allow_restart_session
               OR revision <> 1
            LIMIT 1
            """
        )
    ).first():
        raise RuntimeError("010 downgrade would erase non-default phase-3 values")
    if connection.execute(
        sa.text(
            """
            SELECT 1 FROM widget_groups
            WHERE allow_restart_session
            LIMIT 1
            """
        )
    ).first():
        raise RuntimeError("010 downgrade would erase non-default phase-3 values")
    if connection.execute(
        sa.text("SELECT 1 FROM users WHERE amocrm_group_id IS NOT NULL LIMIT 1")
    ).first():
        raise RuntimeError("010 downgrade would erase non-default phase-3 values")

    rows = connection.execute(
        sa.text("SELECT name, name_key FROM widget_groups")
    ).mappings()
    if any(row["name_key"] != _normalize_group_name(row["name"]) for row in rows):
        raise RuntimeError("010 downgrade would erase non-default phase-3 values")


def upgrade() -> None:
    op.add_column(
        "widget_settings", sa.Column("support_phone", sa.String(64), nullable=True)
    )
    op.add_column(
        "widget_settings",
        sa.Column(
            "allowed_statuses",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[\"working\", \"break\", \"finished\"]'::json"),
        ),
    )
    op.add_column(
        "widget_settings",
        sa.Column(
            "default_allow_restart_session",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "widget_settings",
        sa.Column(
            "revision", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
    )
    op.add_column(
        "widget_groups", sa.Column("name_key", sa.String(255), nullable=True)
    )
    op.add_column(
        "widget_groups",
        sa.Column(
            "allow_restart_session",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column("users", sa.Column("amocrm_group_id", sa.Integer(), nullable=True))

    _backfill_group_name_keys()
    op.alter_column("widget_groups", "name_key", nullable=False)
    op.create_unique_constraint(
        "uq_widget_groups_account_name_key",
        "widget_groups",
        ["account_id", "name_key"],
    )


def downgrade() -> None:
    _reject_non_default_phase_3_values()
    op.drop_constraint(
        "uq_widget_groups_account_name_key", "widget_groups", type_="unique"
    )
    op.drop_column("users", "amocrm_group_id")
    op.drop_column("widget_groups", "allow_restart_session")
    op.drop_column("widget_groups", "name_key")
    op.drop_column("widget_settings", "revision")
    op.drop_column("widget_settings", "default_allow_restart_session")
    op.drop_column("widget_settings", "allowed_statuses")
    op.drop_column("widget_settings", "support_phone")
