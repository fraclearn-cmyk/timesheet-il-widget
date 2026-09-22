"""Add durable status commands and group-local business dates.

Historical sessions without an active group use UTC for their business date.
Existing duplicate open sessions abort migration with their account/user scope;
history is never silently consolidated.

Revision ID: 011
Revises: 010
"""

from zoneinfo import ZoneInfo

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    duplicate = conn.execute(sa.text("""
        SELECT amocrm_account_id, amocrm_user_id, count(*) AS n
        FROM work_sessions WHERE end_time IS NULL
        GROUP BY amocrm_account_id, amocrm_user_id HAVING count(*) > 1
        ORDER BY amocrm_account_id, amocrm_user_id LIMIT 1
    """)).mappings().first()
    if duplicate:
        raise RuntimeError(f"duplicate open work_sessions for account {duplicate['amocrm_account_id']}, user {duplicate['amocrm_user_id']}: {duplicate['n']}")
    op.add_column("work_sessions", sa.Column("business_date", sa.Date(), nullable=True))
    rows = conn.execute(sa.text("""
        SELECT s.id, s.start_time, g.timezone, g.work_start_time, g.work_end_time
        FROM work_sessions s
        LEFT JOIN users u ON u.amocrm_account_id=s.amocrm_account_id AND u.amocrm_user_id=s.amocrm_user_id
        LEFT JOIN group_members m ON m.account_id=s.amocrm_account_id AND m.user_id=u.id AND m.is_active=true
        LEFT JOIN widget_groups g ON g.id=m.group_id AND g.account_id=m.account_id AND g.is_active=true
        ORDER BY s.id
    """)).mappings().all()
    for row in rows:
        zone = row["timezone"] or "UTC"
        local = row["start_time"].replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(zone))
        day = local.date()
        if row["work_start_time"] and row["work_end_time"] and row["work_start_time"] > row["work_end_time"] and local.time() < row["work_end_time"]:
            from datetime import timedelta
            day -= timedelta(days=1)
        conn.execute(sa.text("UPDATE work_sessions SET business_date=:day WHERE id=:id"), {"day": day, "id": row["id"]})
    op.create_index("uq_work_sessions_open_account_user", "work_sessions", ["amocrm_account_id", "amocrm_user_id"], unique=True, postgresql_where=sa.text("end_time IS NULL"), sqlite_where=sa.text("end_time IS NULL"))
    op.create_table("timesheet_commands",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("amocrm_user_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("account_id", "amocrm_user_id", "key", name="uq_timesheet_commands_scope_key"))


def downgrade() -> None:
    conn = op.get_bind()
    if conn.scalar(sa.text("SELECT count(*) FROM timesheet_commands")):
        raise RuntimeError("cannot downgrade phase-4 data without erasing commands")
    op.drop_table("timesheet_commands")
    op.drop_index("uq_work_sessions_open_account_user", table_name="work_sessions")
    op.drop_column("work_sessions", "business_date")
