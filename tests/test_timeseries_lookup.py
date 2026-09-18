"""TimeSeries must select exactly what the old linear scan selected.

Root cause (production soak 2026-09-18): the book/depth/vantage buffers were
deques scanned linearly under the global _data_lock for "newest sample at or
before t". While the consumer keeps up, t is the newest timestamp and the scan
stops immediately. Once the consumer falls behind, t is an OLD event timestamp
while the buffer holds RECENT samples, so every event walked almost the entire
8192-entry buffer with the lock held - being behind made each event vastly more
expensive, which put it further behind. Measured: 82/s -> 1250/s market surge,
consumer collapsed 150/s -> 18/s, 1.35M causally-required events shed.

Correctness is non-negotiable: for the same timestamp the same sample must be
chosen, and a future sample must never be selected.
"""
from __future__ import annotations

import random
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from waverun_live import TimeSeries  # noqa: E402

T = datetime(2026, 1, 1, tzinfo=UTC)


def _linear(keys, rows, t, where=None):
    """The original semantics: newest-first, first match wins."""
    for key, row in zip(reversed(keys), reversed(rows)):
        if key <= t and (where is None or where(row)):
            return row
    return None


def test_matches_the_linear_scan_for_every_query():
    random.seed(3)
    keys = [T + timedelta(milliseconds=i * 250) for i in range(500)]
    rows = [{'i': i} for i in range(500)]
    series = TimeSeries(8192)
    for k, r in zip(keys, rows):
        series.append(k, r)
    for _ in range(4000):
        t = T + timedelta(milliseconds=random.uniform(-2000, 130000))
        assert series.at(t) == _linear(keys, rows, t)


def test_never_selects_a_future_sample():
    series = TimeSeries(8192)
    for i in range(200):
        series.append(T + timedelta(seconds=i), {'i': i})
    t = T + timedelta(seconds=50, milliseconds=500)
    picked = series.at(t)
    assert picked == {'i': 50}, 'must select the newest sample at or before t'


def test_secondary_predicate_matches_linear_scan():
    """The vantage lookup also requires the broker stamp to be <= t."""
    random.seed(5)
    keys, rows = [], []
    series = TimeSeries(8192)
    for i in range(400):
        arrival = T + timedelta(milliseconds=i * 200)
        # broker stamp lags arrival by a random amount, as a real quote does
        stamp = arrival - timedelta(milliseconds=random.uniform(0, 400))
        row = {'timestamp': stamp, 'i': i}
        keys.append(arrival); rows.append(row); series.append(arrival, row)
    for _ in range(2000):
        t = T + timedelta(milliseconds=random.uniform(0, 80000))
        where = lambda row: row['timestamp'] <= t  # noqa: E731
        assert series.at(t, where=where) == _linear(keys, rows, t, where)


def test_respects_maxlen():
    series = TimeSeries(100)
    for i in range(500):
        series.append(T + timedelta(seconds=i), {'i': i})
    assert len(series) == 100
    assert series.at(T + timedelta(seconds=499)) == {'i': 499}
    assert series.at(T + timedelta(seconds=10)) is None, 'evicted samples are gone'


def test_lookup_cost_does_not_grow_when_the_consumer_falls_behind():
    """The actual regression: a far-behind query must not walk the buffer."""
    series = TimeSeries(8192)
    for i in range(8192):
        series.append(T + timedelta(milliseconds=i * 100), {'i': i})
    behind = T + timedelta(milliseconds=50)      # ~8000 samples behind
    caught_up = T + timedelta(milliseconds=8191 * 100)

    def timed(t):
        start = time.perf_counter()
        for _ in range(2000):
            series.at(t)
        return time.perf_counter() - start

    slow, fast = timed(behind), timed(caught_up)
    assert slow < fast * 25, (
        f'falling behind must not blow up lookup cost (behind {slow:.4f}s vs caught-up {fast:.4f}s)')
