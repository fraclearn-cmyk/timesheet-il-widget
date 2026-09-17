"""Confirmed activity requires evidence, attribution and a WORKING window."""

from datetime import datetime, timedelta, timezone
import importlib

import pytest

from app.models import WorkSession, WorkStatus, User, CrmEvent, StatusTransition

START = datetime(2026, 9, 16, 8)


def factory():
    module = importlib.import_module("app.models.activity_interval")
    assert hasattr(module.ActivityInterval, "from_evidence"), "domain factory missing"
    return module.ActivityInterval.from_evidence


def session(status=WorkStatus.WORKING):
    user = User(id=7, amocrm_user_id=700, amocrm_account_id=100, name="One")
    work = WorkSession(id=1, user_name="One", start_time=START, current_status=status)
    work.amocrm_user_id = 700
    work.amocrm_account_id = 100
    work.user = user
    return work


def evidence(user_id=7):
    event = CrmEvent(
        account_id=100,
        user_id=user_id,
        event_type="lead_added",
        author_amocrm_user_id=700,
        occurred_at=START,
        is_complete=1,
    )
    event.external_id = "opaque-A1"
    return event


@pytest.mark.parametrize("status", [WorkStatus.BREAK, WorkStatus.FINISHED])
def test_confirmed_activity_is_rejected_outside_working(status):
    with pytest.raises(ValueError, match="WORKING"):
        factory()(
            session(status),
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source="crm_event",
            evidence=evidence(),
        )


def test_browser_input_is_unconfirmed():
    interval = factory()(
        session(),
        started_at=START,
        ended_at=START + timedelta(seconds=30),
        source="unconfirmed_input",
    )
    assert interval.kind == "unconfirmed"
    assert interval.source == "unconfirmed_input"
    assert interval.user_id == 7


@pytest.mark.parametrize("user_id", [None, 0, -1, 8])
def test_confirmed_activity_requires_matching_known_author(user_id):
    with pytest.raises(ValueError, match="attribution"):
        factory()(
            session(),
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source="crm_event",
            evidence=evidence(user_id),
        )


def test_valid_crm_evidence_creates_confirmed_interval():
    interval = factory()(
        session(),
        started_at=START,
        ended_at=START + timedelta(seconds=30),
        source="crm_event",
        evidence=evidence(),
    )
    assert interval.kind == "confirmed"
    assert interval.source == "crm_event"
    assert interval.account_id == 100
    assert interval.user_id == 7


def test_interval_cannot_cross_a_break_even_after_resume():
    work = session()
    work.status_transitions = [
        StatusTransition(to_status="break", timestamp=START + timedelta(seconds=10)),
        StatusTransition(to_status="working", timestamp=START + timedelta(seconds=20)),
    ]
    with pytest.raises(ValueError, match="WORKING"):
        factory()(
            work,
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source="crm_event",
            evidence=evidence(),
        )


@pytest.mark.parametrize("source", ["browser_input", "mouse", "call", "crm_event"])
def test_unsupported_or_unproven_sources_cannot_create_confirmed_activity(source):
    with pytest.raises(ValueError):
        factory()(
            session(),
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source=source,
        )


def test_interval_cannot_run_backwards():
    with pytest.raises(ValueError):
        factory()(
            session(),
            started_at=START,
            ended_at=START - timedelta(seconds=1),
            source="unconfirmed_input",
        )


@pytest.mark.parametrize("raw_author", [0, -1, 701])
def test_system_or_mismatched_external_author_cannot_be_attributed(raw_author):
    event = evidence()
    event.author_amocrm_user_id = raw_author
    with pytest.raises(ValueError, match="attribution"):
        factory()(
            session(),
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source="crm_event",
            evidence=event,
        )


def test_measured_call_is_confirmed_but_unknown_duration_is_not():
    from app.models import CallEvent

    call = CallEvent(
        account_id=100,
        user_id=7,
        author_amocrm_user_id=700,
        source_event_id="call-one",
        direction="incoming",
        occurred_at=START,
        duration_seconds=30,
    )
    interval = factory()(
        session(),
        started_at=START,
        ended_at=START + timedelta(seconds=30),
        source="call",
        evidence=call,
    )
    assert interval.kind == "confirmed"
    assert interval.duration_source == "observed"
    call.duration_seconds = None
    with pytest.raises(ValueError):
        factory()(
            session(),
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source="call",
            evidence=call,
        )


def test_timezone_aware_window_and_mixed_transition_timestamps_are_utc():
    local_start = datetime(2026, 9, 16, 11, tzinfo=timezone(timedelta(hours=3)))
    work = session()
    work.status_transitions = [
        StatusTransition(to_status="working", timestamp=local_start),
        StatusTransition(to_status="working", timestamp=START + timedelta(hours=1)),
    ]
    interval = factory()(
        work,
        started_at=local_start,
        ended_at=local_start + timedelta(seconds=30),
        source="crm_event",
        evidence=evidence(),
    )
    assert interval.started_at == START
    assert interval.ended_at == START + timedelta(seconds=30)


@pytest.mark.parametrize("raw_author", [0, -1])
def test_system_author_cannot_be_confirmed_even_if_a_legacy_user_matches(raw_author):
    work = session()
    work.amocrm_user_id = raw_author
    work.user.amocrm_user_id = raw_author
    event = evidence()
    event.author_amocrm_user_id = raw_author
    with pytest.raises(ValueError, match="attribution"):
        factory()(
            work,
            started_at=START,
            ended_at=START + timedelta(seconds=30),
            source="crm_event",
            evidence=event,
        )
