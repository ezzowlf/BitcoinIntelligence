"""The entry quote must come from the evaluation, not from a racing table read.

Root cause (production 2026-09-18): register_many() re-derived the entry
bid/ask with `SELECT ... FROM quotes WHERE t<=?`, but the Vantage recorder
thread commits that same quote asynchronously. When registration won the
race the row was stored with NULL bid/ask, which resolves permanently as
INVALID_DATA with entry=None. 17 of 183 NULL-entry observations had a quote
inside max_gap by the time they were inspected - the price was lost to write
ordering, not to a real market gap.
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import waverun_live  # noqa: E402
from test_waverun_b2_degraded_e2e import _spot_trade  # noqa: E402

T = datetime(2026, 1, 1, tzinfo=UTC)
BID, ASK = 77000.0, 77010.0


@pytest.fixture
def session(tmp_path):
    rt = tmp_path / 'runtime' / 'waverun'; rt.mkdir(parents=True); (tmp_path / 'database').mkdir()
    s = waverun_live.LiveSession(output=rt / 'latest.json', database=tmp_path / 'database' / 'p.db',
                                 symbol='btcusdt', mt5_values={'MT5_ENABLED': 'false'})
    s._JSONL_HEARTBEAT_S = 0.0; s._JOURNAL_HEARTBEAT_S = 0.0; s._OUTCOME_SAMPLE_S = 0.0
    s.mt5.tick = lambda: _quote(datetime.now(UTC))
    return s, rt


def _quote(stamp):
    return {'status': 'AVAILABLE', 'bid': BID, 'ask': ASK, 'spread': ASK - BID,
            'timestamp': stamp.isoformat(), 'time_msc': int(stamp.timestamp() * 1000)}


def _observations(session):
    with session.journal.connect() as db:
        return db.execute('SELECT id,horizon,bid,ask FROM observations').fetchall()


def test_entry_quote_survives_an_empty_quotes_table(session):
    s, rt = session
    # The in-memory sample is stamped with wall-clock arrival, so the events
    # have to sit on the same timeline for the evaluation to select it.
    base = datetime.now(UTC)
    s._record_vantage_tick()          # the evaluation now has a fresh quote in memory
    with s.journal.connect() as db:   # simulate the recorder not having committed yet
        db.execute('DELETE FROM quotes')

    async def run():
        for i in range(5):
            await s.on_event(_spot_trade(base + timedelta(seconds=i + 1), 77000 + i))
    asyncio.run(run())

    rows = _observations(s)
    assert rows, 'expected the evaluation to register observations'
    priced = [r for r in rows if r[2] is not None and r[3] is not None]
    assert priced, 'entry quote was lost although the evaluation held a fresh one'
    for _, _, bid, ask in priced:
        assert (bid, ask) == (BID, ASK), 'entry must be the quote the signal was evaluated on'


def test_stale_quote_still_fails_closed(session):
    """Freshness is unchanged: a quote older than max_gap must not become an
    entry price just because it is held in memory."""
    s, rt = session
    stale = datetime.now(UTC) - timedelta(seconds=s.outcomes.max_gap + 30)
    s.mt5.tick = lambda: _quote(stale)
    base = datetime.now(UTC)
    s._record_vantage_tick()
    with s.journal.connect() as db:
        db.execute('DELETE FROM quotes')

    async def run():
        for i in range(5):
            await s.on_event(_spot_trade(base + timedelta(seconds=i + 1), 77000 + i))
    asyncio.run(run())

    for _, _, bid, ask in _observations(s):
        assert bid is None and ask is None, 'a stale quote must not be used as an entry price'


def test_outcome_scheduler_reports_progress_between_heavy_steps(session):
    """Regression: the liveness marker was only written at the end of
    resolve_due(), so a slow-but-healthy housekeeping pass aged it past the
    10s outcomes_ready window and cancelled every in-flight setup."""
    s, _ = session
    from bitcoin_cycle_analyzer.short_term.journal import Journal
    s._mark_outcome_progress()
    first = Journal.progress_at(s.journal.path)['outcome_scheduler']
    s._mark_outcome_progress()
    second = Journal.progress_at(s.journal.path)['outcome_scheduler']
    assert second['seq'] > first['seq'], 'each completed step must advance liveness'
    assert second['committed_at'] >= first['committed_at']
