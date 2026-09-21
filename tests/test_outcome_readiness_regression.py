"""Regression guard for the outcome-evidence gate (2026-09-21).

`outcomes_ready` answers one question: is outcome resolution alive and recent?
It was implemented as `0 <= received - committed_at <= 10`, which additionally
demanded that the evaluated event be NEWER than the outcome scheduler's last
heartbeat. Those timestamps come from two independent sources - the scheduler
heartbeats roughly once a second from wall time, while `received` is when a
trade arrived and evaluation is gated to once per received second - so whenever
the scheduler beat between an event arriving and that second being evaluated,
the difference went negative and outcome evidence was reported missing although
the scheduler was healthy.

Measured in production before the fix: 20 of 25 samples negative (median
-0.437s), and `outcomes` in missing_evidence for 46 of the last 60 signal
transitions. Since SignalEngine cancels a setup whenever `missing` is non-empty,
this silently suppressed otherwise-valid setups.

The bound itself (10s) is unchanged; it is simply applied symmetrically.
"""
from __future__ import annotations

import pytest


def outcome_ready(received_ts: float, committed_at: float) -> bool:
    """Mirror of the production expression in scripts/waverun_live.py."""
    return abs(received_ts - committed_at) <= 10


BASE = 1_790_000_000.0


@pytest.mark.parametrize("delta", [-0.437, -1.718, -0.001, -9.9])
def test_scheduler_heartbeat_slightly_ahead_still_counts_as_ready(delta):
    """The exact incident signature: heartbeat marginally ahead of the event."""
    assert outcome_ready(BASE + delta, BASE) is True


@pytest.mark.parametrize("delta", [0.0, 0.32, 5.0, 9.9])
def test_event_newer_than_heartbeat_is_ready_as_before(delta):
    """Unchanged behaviour for the cases that already worked."""
    assert outcome_ready(BASE + delta, BASE) is True


@pytest.mark.parametrize("delta", [10.1, 60.0, 3600.0])
def test_a_stalled_scheduler_is_still_detected(delta):
    """A genuinely dead scheduler stops heartbeating, the gap grows past the
    bound, and outcome evidence must go missing exactly as before."""
    assert outcome_ready(BASE + delta, BASE) is False


@pytest.mark.parametrize("delta", [-10.1, -60.0, -3600.0])
def test_a_wildly_skewed_heartbeat_is_still_rejected(delta):
    """abs() must not become a licence for an arbitrarily future heartbeat -
    a clock jump that large is not 'recent' in either direction."""
    assert outcome_ready(BASE + delta, BASE) is False


def test_bound_is_symmetric_and_still_ten_seconds():
    assert outcome_ready(BASE - 10.0, BASE) is True
    assert outcome_ready(BASE + 10.0, BASE) is True
    assert outcome_ready(BASE - 10.001, BASE) is False
    assert outcome_ready(BASE + 10.001, BASE) is False


def test_production_expression_matches_this_guard():
    """Pin the guard to the real source line, so the two cannot drift apart."""
    from pathlib import Path

    source = Path(__file__).resolve().parents[1] / "scripts/waverun_live.py"
    text = source.read_text(encoding="utf8")
    assert (
        "outcome_ready='outcome_scheduler' in markers and "
        "abs(received.timestamp()-markers['outcome_scheduler']['committed_at'])<=10"
    ) in text
