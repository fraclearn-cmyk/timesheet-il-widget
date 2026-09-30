"""PostgreSQL plan and migration checks for the phase-8 access paths."""

from alembic import command
from sqlalchemy import inspect, text

from test_migrations import migrated_db as _postgres_fixture


migrated_db = _postgres_fixture


EXPECTED_INDEXES = {
    "work_sessions": {
        "ix_work_sessions_account_user_business_date": (
            "amocrm_account_id",
            "amocrm_user_id",
            "business_date",
        ),
    },
    "status_transitions": {
        "ix_status_transitions_session_timestamp_id": (
            "work_session_id",
            "timestamp",
            "id",
        ),
    },
}

QUERIES = {
    "team": """SELECT * FROM work_sessions
        WHERE amocrm_account_id=20 AND amocrm_user_id=5
          AND start_time < timestamp '2026-10-01'
          AND (end_time IS NULL OR end_time > timestamp '2026-09-01')""",
    "activity": """SELECT * FROM activity_intervals
        WHERE account_id=20 AND user_id=195 AND kind='confirmed'
          AND started_at < timestamp '2026-10-01'
          AND ended_at >= timestamp '2026-09-01'""",
    "report": """SELECT id,business_date FROM work_sessions
        WHERE amocrm_account_id=20 AND amocrm_user_id=5
          AND business_date BETWEEN date '2026-09-01' AND date '2026-09-30'""",
    "status": """SELECT * FROM status_transitions
        WHERE work_session_id BETWEEN 8551 AND 8560
        ORDER BY work_session_id,timestamp,id""",
    "membership": """SELECT user_id FROM group_members
        WHERE account_id=20 AND group_id=20 AND is_active""",
    "due": """SELECT o.account_id FROM oauth_connections o
        LEFT JOIN ingestion_cursors i ON i.account_id=o.account_id
        WHERE o.is_active AND (i.account_id IS NULL OR i.next_poll_at <= now())
        ORDER BY o.account_id""",
    "cleanup": """SELECT id FROM raw_ingestion_events
        WHERE expires_at <= timestamp '2026-09-30'
        ORDER BY id LIMIT 1000""",
}


def _indexes(engine, table_name):
    return {
        item["name"]: tuple(item["column_names"])
        for item in inspect(engine).get_indexes(table_name)
    }


def _plan(connection, sql):
    payload = connection.execute(
        text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + sql)
    ).scalar_one()
    return payload[0]


def _index_names(node):
    names = {node["Index Name"]} if node.get("Index Name") else set()
    for child in node.get("Plans", []):
        names.update(_index_names(child))
    return names


def _relation_names(node):
    names = {node["Relation Name"]} if node.get("Relation Name") else set()
    for child in node.get("Plans", []):
        names.update(_relation_names(child))
    return names


def _plans(connection):
    return {name: _plan(connection, sql) for name, sql in QUERIES.items()}


def test_014_adds_only_the_proven_composite_indexes_and_roundtrips(migrated_db):
    config, engine = migrated_db
    command.upgrade(config, "head")

    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "014"
        )
    for table_name, expected in EXPECTED_INDEXES.items():
        actual = _indexes(engine, table_name)
        for name, columns in expected.items():
            assert actual.get(name) == columns

    command.downgrade(config, "013")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "013"
        )
    for table_name, expected in EXPECTED_INDEXES.items():
        actual = _indexes(engine, table_name)
        assert expected.keys().isdisjoint(actual)

    command.upgrade(config, "head")
    with engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version")) == "014"
        )


def test_representative_phase5_to_phase7_queries_use_measured_access_paths(
    migrated_db,
):
    """Keep the EXPLAIN evidence tied to representative 40-account cardinality.

    A disposable PostgreSQL 15 probe measured the same query shapes before and
    after the candidate indexes. The accepted indexes reduced the report plan
    from 5.796 ms to 3.068 ms and status history from 4.945 ms to 0.081 ms.
    Activity, membership, due-account and cleanup candidates did not improve
    their existing plans and therefore are deliberately absent from migration 014.
    """
    config, engine = migrated_db
    command.upgrade(config, "013")
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
                INSERT INTO users
                  (id,amocrm_user_id,amocrm_account_id,name,role,is_active,
                   hide_widget,created_at,updated_at)
                SELECT (a-1)*10+u,u,a,'User '||u,'employee',true,false,now(),now()
                FROM generate_series(1,40) a CROSS JOIN generate_series(1,10) u;
                INSERT INTO widget_groups
                  (id,account_id,name,name_key,timezone,work_start_time,
                   work_end_time,is_active,allow_restart_session,created_at,updated_at)
                SELECT a,a,'Group','group','UTC','09:00','18:00',true,false,now(),now()
                FROM generate_series(1,40) a;
                INSERT INTO group_members
                  (account_id,group_id,user_id,is_active,track_time,hide_widget,
                   created_at,updated_at)
                SELECT a,a,(a-1)*10+u,true,true,false,now(),now()
                FROM generate_series(1,40) a CROSS JOIN generate_series(1,10) u;
                INSERT INTO work_sessions
                  (amocrm_account_id,amocrm_user_id,user_name,start_time,end_time,
                   business_date,current_status,total_work_time,total_break_time,
                   break_count,active_duration,unconfirmed_duration,break_duration,
                   idle_duration,created_at,updated_at)
                SELECT a,u,'User '||u,d+time '09:00',d+time '18:00',d,'finished',
                       28800,3600,1,28800,0,3600,0,now(),now()
                FROM generate_series(1,40) a CROSS JOIN generate_series(1,10) u
                CROSS JOIN generate_series(
                    date '2026-08-17',date '2026-09-30',interval '1 day'
                ) d;
                INSERT INTO status_transitions
                  (work_session_id,from_status,to_status,timestamp,duration)
                SELECT id,NULL,'working',start_time,0 FROM work_sessions;
                INSERT INTO activity_intervals
                  (account_id,user_id,work_session_id,started_at,ended_at,kind,
                   source,duration_source,created_at)
                SELECT w.amocrm_account_id,u.id,w.id,w.start_time,w.end_time,
                       'confirmed','call','observed',now()
                FROM work_sessions w JOIN users u
                  ON u.amocrm_account_id=w.amocrm_account_id
                 AND u.amocrm_user_id=w.amocrm_user_id;
                INSERT INTO raw_ingestion_events
                  (account_id,source,external_id,occurred_at,dedup_key,payload,
                   received_at,expires_at,normalization_status)
                SELECT ((n-1)%40)+1,'crm_event',n::text,now(),
                       md5(n::text)||md5(n::text),'{}',
                       timestamp '2026-08-01'+n*interval '1 second',
                       timestamp '2026-09-01'+n*interval '1 second','complete'
                FROM generate_series(1,20000) n;
                ANALYZE;
                """
            )
        )
        baseline = _plans(connection)

    new_index_names = {
        name for indexes in EXPECTED_INDEXES.values() for name in indexes
    }
    for plan in baseline.values():
        assert new_index_names.isdisjoint(_index_names(plan["Plan"]))

    command.upgrade(config, "014")
    with engine.begin() as connection:
        connection.execute(text("ANALYZE"))
        indexed = _plans(connection)

    assert "ix_work_sessions_account_user_business_date" in _index_names(
        indexed["team"]["Plan"]
    )
    assert "ix_work_sessions_account_user_business_date" in _index_names(
        indexed["report"]["Plan"]
    )
    assert "ix_status_transitions_session_timestamp_id" in _index_names(
        indexed["status"]["Plan"]
    )
    assert "ix_activity_intervals_user_id" in _index_names(indexed["activity"]["Plan"])
    assert "uq_group_members_active_account_user" in _index_names(
        indexed["membership"]["Plan"]
    )
    assert "ix_raw_ingestion_events_id" in _index_names(indexed["cleanup"]["Plan"])
    assert _relation_names(indexed["due"]["Plan"]) == {
        "ingestion_cursors",
        "oauth_connections",
    }
    for name, plan in indexed.items():
        assert plan["Execution Time"] < 250, (name, plan)
