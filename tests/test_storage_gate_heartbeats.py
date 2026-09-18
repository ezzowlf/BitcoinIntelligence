"""Regression tests for the storage-gate heartbeats (<=100MB/24h).

Root cause these lock in (production audit 2026-09-18, 31.5GB of persistent
data): a routine BLOCKED/WATCH second - which is almost every evaluated
second - used to write a full row to four JSONL streams, three journal
`events` rows, six predictions rows and fifteen outcome observations. None of
it was read back for a routine second; all of it was permanent.

A real candidate must still persist immediately and in full, so these tests
assert both directions: routine seconds are throttled, relevant ones are not.
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import waverun_live  # noqa: E402
from bitcoin_cycle_analyzer.short_term.journal import Journal  # noqa: E402
from test_waverun_b2_degraded_e2e import _spot_trade as _spot  # noqa: E402

T = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture
def session(tmp_path):
    rt = tmp_path / 'runtime' / 'waverun'; rt.mkdir(parents=True); (tmp_path / 'database').mkdir()
    s = waverun_live.LiveSession(output=rt / 'latest.json', database=tmp_path / 'database' / 'p.db',
                                 symbol='btcusdt', mt5_values={'MT5_ENABLED': 'false'})
    s.mt5.tick = lambda: {'status': 'AVAILABLE', 'bid': 77000., 'ask': 77010.,
                          'timestamp': datetime.now(UTC).isoformat(),
                          'time_msc': int(datetime.now(UTC).timestamp() * 1000)}
    return s, rt, tmp_path / 'database' / 'p.db'


def _feed(s, n, start=0):
    async def run():
        for i in range(n):
            await s.on_event(_spot(T + timedelta(seconds=start + i), 77000 + i))
    asyncio.run(run())


def test_routine_seconds_do_not_write_a_row_per_second(session):
    s, rt, _ = session
    _feed(s, 60)
    # 60 evaluated seconds of routine BLOCKED/WATCH inside one heartbeat window.
    for name in ('pre_gate_candidates', 'decision_records', 'latency_records'):
        rows = sum(1 for _ in (rt / f'{name}.jsonl').open())
        assert rows <= 2, f'{name}: routine seconds must be throttled, got {rows} rows'


def test_routine_seconds_still_advance_liveness_every_second(session):
    """Throttling persistence must not throttle health: feature/candidate/
    decision/prediction liveness is what the supervisor reads to decide the
    pipeline is alive, and it must advance on every evaluated second."""
    s, rt, _ = session
    _feed(s, 30)
    progress = Journal.progress_at(s.journal.path)
    for stage in ('features', 'candidates', 'decisions', 'predictions'):
        assert progress[stage]['seq'] >= 25, f'{stage} liveness must advance per second'


def test_routine_seconds_write_no_permanent_stage_rows(session):
    s, rt, _ = session
    _feed(s, 30)
    with s.journal.connect() as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind LIKE 'stage_%'").fetchone()[0] == 0


def test_routine_seconds_do_not_register_outcome_observations_per_second(session):
    """Outcome observations were the largest single producer: 15/s, each
    resolving into a permanent `outcome` row (~1.3M rows/day)."""
    s, rt, db_path = session
    _feed(s, 60)
    with s.journal.connect() as db:
        observations = db.execute('SELECT count(*) FROM observations').fetchone()[0]
    assert observations <= 30, f'expected one sampled registration set, got {observations}'
    with sqlite3.connect(db_path) as con:
        predictions = con.execute('SELECT count(*) FROM predictions').fetchone()[0]
    assert predictions <= 12, f'expected one sampled forecast set, got {predictions}'


def test_a_relevant_decision_is_always_persisted_immediately(session, monkeypatch):
    """The throttle must never delay or drop a real candidate."""
    s, rt, db_path = session
    _feed(s, 5)
    baseline = sum(1 for _ in (rt / 'decision_records.jsonl').open())
    real = waverun_live.fast_decision
    monkeypatch.setattr(waverun_live, 'fast_decision',
                        lambda *a, **k: _armed(real(*a, **k)))
    _feed(s, 3, start=100)
    after = sum(1 for _ in (rt / 'decision_records.jsonl').open())
    assert after >= baseline + 3, 'every relevant decision must persist immediately'
    with s.journal.connect() as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind='decision'").fetchone()[0] >= 3


def _armed(decision):
    object.__setattr__(decision, 'decision', 'ARMED') if hasattr(decision, '__dataclass_fields__') else setattr(decision, 'decision', 'ARMED')
    return decision
