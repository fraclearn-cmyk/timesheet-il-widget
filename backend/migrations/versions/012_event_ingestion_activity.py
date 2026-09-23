"""Add account-scoped event ingestion persistence.

Revision ID: 012
Revises: 011
"""

from alembic import op
import sqlalchemy as sa


revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ingestion_cursors",
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("last_created_at", sa.DateTime(), nullable=True),
        sa.Column("last_event_id", sa.String(255), nullable=True),
        sa.Column("next_poll_at", sa.DateTime(), nullable=False),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("lease_owner", sa.String(128), nullable=True),
        sa.Column("lease_until", sa.DateTime(), nullable=True),
        sa.Column("webhook_key_hash", sa.String(64), nullable=True),
        sa.Column("encrypted_webhook_key", sa.String(), nullable=True),
        sa.CheckConstraint(
            "failure_count >= 0", name="ck_ingestion_cursors_failure_count"
        ),
        sa.CheckConstraint(
            "webhook_key_hash IS NULL OR " "webhook_key_hash ~ '^[0-9a-f]{64}$'",
            name="ck_ingestion_cursors_webhook_hash",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["oauth_connections.account_id"]),
        sa.PrimaryKeyConstraint("account_id"),
        sa.UniqueConstraint(
            "webhook_key_hash", name="uq_ingestion_cursors_webhook_key_hash"
        ),
    )
    op.create_index(
        "ix_ingestion_cursors_next_poll_at",
        "ingestion_cursors",
        ["next_poll_at"],
    )
    op.create_index(
        "ix_ingestion_cursors_lease_until", "ingestion_cursors", ["lease_until"]
    )

    op.create_table(
        "raw_ingestion_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("dedup_key", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("received_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("normalization_status", sa.String(30), nullable=False),
        sa.Column("error_code", sa.String(100), nullable=True),
        sa.CheckConstraint(
            "source IN ('crm_event','call')",
            name="ck_raw_ingestion_events_source",
        ),
        sa.CheckConstraint(
            "normalization_status IN ('pending','complete','incomplete')",
            name="ck_raw_ingestion_events_status",
        ),
        sa.CheckConstraint(
            "dedup_key ~ '^[0-9a-f]{64}$'",
            name="ck_raw_ingestion_events_dedup_key",
        ),
        sa.CheckConstraint(
            "expires_at >= received_at",
            name="ck_raw_ingestion_events_expiry",
        ),
        sa.ForeignKeyConstraint(
            ["account_id"], ["oauth_connections.account_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "source",
            "dedup_key",
            name="uq_raw_ingestion_events_scope_dedup",
        ),
    )
    for column in (
        "id",
        "account_id",
        "occurred_at",
        "received_at",
        "expires_at",
        "normalization_status",
    ):
        op.create_index(
            f"ix_raw_ingestion_events_{column}", "raw_ingestion_events", [column]
        )

    op.create_table(
        "event_type_catalog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(100), nullable=False),
        sa.Column("label", sa.String(255), nullable=True),
        sa.Column("refreshed_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["account_id"], ["oauth_connections.account_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id", "event_key", name="uq_event_type_catalog_account_key"
        ),
    )
    for column in ("id", "account_id", "refreshed_at"):
        op.create_index(
            f"ix_event_type_catalog_{column}", "event_type_catalog", [column]
        )

    op.create_table(
        "presence_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("command_id", sa.Uuid(), nullable=False),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("signal_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "signal_count BETWEEN 1 AND 100000",
            name="ck_presence_batches_signal_count",
        ),
        sa.CheckConstraint(
            "last_seen_at >= window_started_at",
            name="ck_presence_batches_window",
        ),
        sa.ForeignKeyConstraint(
            ["account_id", "user_id"],
            ["users.amocrm_account_id", "users.id"],
            name="fk_presence_batches_account_user",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "account_id",
            "user_id",
            "command_id",
            name="uq_presence_batches_scope_command",
        ),
    )
    for column in ("id", "account_id", "user_id", "window_started_at"):
        op.create_index(f"ix_presence_batches_{column}", "presence_batches", [column])

    op.add_column("crm_events", sa.Column("raw_event_id", sa.Integer(), nullable=True))
    op.add_column(
        "crm_events", sa.Column("original_event_type", sa.String(100), nullable=True)
    )
    op.create_index("ix_crm_events_raw_event_id", "crm_events", ["raw_event_id"])
    op.create_foreign_key(
        "fk_crm_events_raw_event",
        "crm_events",
        "raw_ingestion_events",
        ["raw_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.execute("UPDATE crm_events SET original_event_type=event_type")

    op.add_column("call_events", sa.Column("raw_event_id", sa.Integer(), nullable=True))
    op.add_column(
        "call_events",
        sa.Column("is_complete", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_call_events_raw_event_id", "call_events", ["raw_event_id"])
    op.create_foreign_key(
        "fk_call_events_raw_event",
        "call_events",
        "raw_ingestion_events",
        ["raw_event_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_unique_constraint(
        "uq_call_events_account_source_occurred",
        "call_events",
        ["account_id", "source_event_id", "occurred_at"],
    )
    op.create_check_constraint(
        "ck_call_events_completeness",
        "call_events",
        "is_complete IN (0,1) AND "
        "(is_complete = 0 OR "
        "(user_id IS NOT NULL AND direction IN ('incoming','outgoing') "
        "AND duration_seconds IS NOT NULL))",
    )
    op.create_check_constraint(
        "ck_activity_intervals_duration_source",
        "activity_intervals",
        "duration_source IN ('point','observed','calculated')",
    )


def downgrade() -> None:
    conn = op.get_bind()
    for table in (
        "ingestion_cursors",
        "raw_ingestion_events",
        "event_type_catalog",
        "presence_batches",
    ):
        if conn.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError(
                "cannot downgrade phase-5 ingestion data without erasing records"
            )
    if conn.scalar(
        sa.text(
            "SELECT (SELECT count(*) FROM crm_events WHERE raw_event_id IS NOT NULL) + "
            "(SELECT count(*) FROM call_events WHERE raw_event_id IS NOT NULL)"
        )
    ):
        raise RuntimeError(
            "cannot downgrade phase-5 ingestion data with normalized raw references"
        )

    op.drop_constraint(
        "ck_activity_intervals_duration_source",
        "activity_intervals",
        type_="check",
    )
    op.drop_constraint("ck_call_events_completeness", "call_events", type_="check")
    op.drop_constraint(
        "uq_call_events_account_source_occurred", "call_events", type_="unique"
    )
    op.drop_constraint("fk_call_events_raw_event", "call_events", type_="foreignkey")
    op.drop_index("ix_call_events_raw_event_id", table_name="call_events")
    op.drop_column("call_events", "is_complete")
    op.drop_column("call_events", "raw_event_id")

    op.drop_constraint("fk_crm_events_raw_event", "crm_events", type_="foreignkey")
    op.drop_index("ix_crm_events_raw_event_id", table_name="crm_events")
    op.drop_column("crm_events", "original_event_type")
    op.drop_column("crm_events", "raw_event_id")

    op.drop_table("presence_batches")
    op.drop_table("event_type_catalog")
    op.drop_table("raw_ingestion_events")
    op.drop_table("ingestion_cursors")
