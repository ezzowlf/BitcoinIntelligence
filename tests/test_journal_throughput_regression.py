"""Regression guard for the 2026-09-21 production incident.

Symptom: binance_spot/binance_futures reported OFFLINE on the dashboard with
reconnect_count=0 while both websockets were connected and delivering events
the whole time; SignalEngine emitted REQUIRED_EVIDENCE_UNAVAILABLE with
missing_evidence=[spot,l2,outcomes]; the decision pipeline produced no new
records for ~10 minutes at a time.

Root cause: Journal.connect() opened and closed a fresh sqlite3 connection
(plus two PRAGMA round-trips) for EVERY journal operation, all serialised
behind the single in-process writer gate. Measured at 3.63ms/op against the
live 74MB journal.db, that capped the whole collector at ~275 journal ops/s.
Live BTC trade rates need far more, so the consumer fell permanently behind,
shed trades (severe backpressure -> spot/l2 forced to UNAVAILABLE) and left the
feed_* progress markers' event_at frozen ~600s in the past while committed_at
stayed current.

These tests pin the properties that failure violated. They deliberately assert
on throughput ratio and on the connection-reuse invariant rather than on an
absolute wall-clock budget, so they stay meaningful on slower CI hardware.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from datetime import UTC, datetime

import pytest

from bitcoin_cycle_analyzer.short_term.journal import Journal, identity


@pytest.fixture()
def journal(tmp_path):
    return Journal(tmp_path / "journal.db")


def test_connect_reuses_one_connection(journal):
    """The incident's direct cause: a new connection per operation."""
    seen = []
    for _ in range(5):
        with journal.connect() as db:
            seen.append(id(db))
    assert len(set(seen)) == 1, "Journal.connect() must reuse a single connection"


def test_nested_connect_does_not_open_a_second_writer(journal):
    """The writer gate is an RLock, so re-entry is possible; re-entering must
    hand back the connection whose transaction is already open instead of
    contending with it."""
    with journal.connect() as outer:
        with journal.connect() as inner:
            assert inner is outer
            inner.execute("SELECT 1")


def test_nested_connect_commits_only_at_the_outermost_frame(journal):
    """An inner `with db:` must not prematurely commit the outer caller's
    still-incomplete unit of work."""
    with pytest.raises(RuntimeError):
        with journal.connect() as db:
            db.execute("INSERT INTO state VALUES('k','1')")
            with journal.connect() as inner:
                inner.execute("INSERT INTO state VALUES('k2','2')")
            raise RuntimeError("abort the outer transaction")
    # Both writes belonged to the one outer transaction, so both rolled back.
    assert journal.state("k") is None
    assert journal.state("k2") is None


def test_failed_statement_does_not_poison_the_cached_connection(journal):
    with pytest.raises(sqlite3.Error):
        with journal.connect() as db:
            db.execute("SELECT * FROM table_that_does_not_exist")
    # The next caller must get a working connection, not inherit the fault.
    with journal.connect() as db:
        assert db.execute("SELECT count(*) FROM progress").fetchone() is not None


def test_mark_throughput_far_exceeds_the_incident_ceiling(journal):
    """The collector marks feed liveness once per second per source on top of
    per-event evaluation writes. At the incident's ~275 ops/s ceiling the whole
    process could not keep up with live trade rates."""
    now = datetime.now(UTC)
    count = 400
    started = time.monotonic()
    for i in range(count):
        journal.mark("feed_spot", identity("spot", i), now)
    ops_per_second = count / (time.monotonic() - started)
    assert ops_per_second > 1000, f"journal marks capped at {ops_per_second:.0f} ops/s"


def test_concurrent_writers_do_not_serialise_into_a_stall(journal):
    """Several independent workers (feed consumers, outcome scheduler, raw
    writer, Vantage recorder) write concurrently in production."""
    now = datetime.now(UTC)
    errors: list[BaseException] = []

    def worker(index: int) -> None:
        try:
            for i in range(60):
                journal.mark(f"feed_{index}", identity(index, i), now)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assert below
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    started = time.monotonic()
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.monotonic() - started

    assert not errors, f"concurrent journal writers failed: {errors[:3]}"
    assert elapsed < 5.0, f"8x60 concurrent marks took {elapsed:.1f}s"


def test_independent_journal_objects_share_the_same_connection(journal, tmp_path):
    """Independently constructed Journals for one database cooperate through the
    shared gate; they must share the reused connection too, or the process ends
    up with one connection per object behind a single gate."""
    twin = Journal(tmp_path / "journal.db")
    with journal.connect() as a:
        pass
    with twin.connect() as b:
        pass
    assert a is b
