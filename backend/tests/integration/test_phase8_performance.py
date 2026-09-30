"""Conservative local SLA checks for the forty-account polling workload."""

from time import perf_counter

from alembic import command
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.services.event_ingestion_service import EventIngestionService
from test_migrations import migrated_db as _postgres_fixture


migrated_db = _postgres_fixture

# This is a regression ceiling, not a production capacity claim. The measured
# warm local PostgreSQL call is below 1 ms; 250 ms leaves ample CI/VM headroom.
FORTY_ACCOUNT_DUE_SCAN_SLA_MS = 250


def test_due_account_scan_is_one_query_and_meets_local_forty_account_sla(
    migrated_db,
):
    config, engine = migrated_db
    command.upgrade(config, "head")
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT INTO oauth_connections
                  (account_id,account_url,encrypted_access_token,
                   encrypted_refresh_token,is_active,created_at,updated_at)
                SELECT a,'https://a'||a||'.example','access','refresh',true,now(),now()
                FROM generate_series(1,40) a;
                INSERT INTO ingestion_cursors (account_id,next_poll_at,failure_count)
                SELECT a,timestamp '2026-09-29',0 FROM generate_series(1,40) a;
                ANALYZE oauth_connections;
                ANALYZE ingestion_cursors;
                """
            )
        )

    selects = 0

    def count_selects(_conn, _cursor, statement, *_args):
        nonlocal selects
        if statement.lstrip().upper().startswith("SELECT"):
            selects += 1

    with Session(engine) as db:
        service = EventIngestionService(db, None, None, owner="phase8-performance")
        from datetime import datetime

        now = datetime(2026, 9, 30)
        for _ in range(3):
            assert service.due_accounts(now) == list(range(1, 41))

        elapsed = []
        event.listen(engine, "before_cursor_execute", count_selects)
        try:
            for _ in range(20):
                started = perf_counter()
                assert service.due_accounts(now) == list(range(1, 41))
                elapsed.append((perf_counter() - started) * 1000)
        finally:
            event.remove(engine, "before_cursor_execute", count_selects)

    assert selects == 20
    elapsed.sort()
    p95 = elapsed[int(len(elapsed) * 0.95) - 1]
    assert p95 < FORTY_ACCOUNT_DUE_SCAN_SLA_MS, {
        "p95_ms": p95,
        "max_ms_diagnostic": max(elapsed),
    }
