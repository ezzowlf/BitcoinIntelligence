"""Regression guard for the feed-health reporting half of the 2026-09-21 incident.

The API's independent freshness cross-check collapsed every degree of feed
lateness into a bare OFFLINE at the 5s proof window, and the ComponentHealth it
substituted discarded the supervisor's real diagnostics (reconnect_count,
last_error and last_event_at all became 0/None). On the dashboard a feed that
was merely behind was therefore indistinguishable from a dead socket, and the
evidence needed to tell them apart had been erased - which is why the incident
presented as "binance_spot=OFFLINE, reconnect_count=0" while the socket was in
fact connected and delivering.

This is the same defect already fixed for the pipeline stages on 2026-09-14
(see web_api._resilience); these tests pin the matching behaviour for feeds.
No LIVE threshold is loosened: proven freshness still means 0..5s.
"""
from __future__ import annotations

import time

import pytest

from bitcoin_cycle_analyzer.short_term.resilience import CONFIG


pytest.importorskip("fastapi")


def _components(
    monkeypatch, tmp_path, marker_age_seconds, supervisor_component=None, markers=None
):
    """Drive web_api._resilience with one synthetic feed_spot marker age."""
    from datetime import UTC, datetime

    from bitcoin_cycle_analyzer.short_term import web_api

    now = datetime.now(UTC)
    now_ts = now.timestamp()
    if markers is None:
        markers = {
            "feed_spot": {
                "seq": 1,
                "event_at": now_ts - marker_age_seconds,
                "committed_at": now_ts - marker_age_seconds,
                "cause_id": "x",
            }
        }
    monkeypatch.setattr(web_api.Journal, "progress_at", staticmethod(lambda _path: markers))
    snapshot = web_api.StateReader.__new__(web_api.StateReader)
    snapshot.runtime = tmp_path
    snapshot.health_path = tmp_path / "health.json"
    # A *fresh* supervisor report, so the cross-check runs against the primary
    # report path rather than the API-side fallback.
    report = {
        "server_time": now.isoformat(),
        "components": {"binance_spot": supervisor_component} if supervisor_component else {},
        "recovery": {"level": 0, "attempts": 0},
    }
    monkeypatch.setattr(web_api, "read_json", lambda _p: report)
    monkeypatch.setattr(web_api.StateReader, "_decision_pipeline_age", lambda self, now: 1.0)

    return snapshot._resilience(now, "LIVE", "LIVE", "LIVE", "LIVE")["components"]


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (2.0, None),                              # proven fresh -> supervisor report kept
        (12.0, "DEGRADED"),                       # behind the proof window, not stale yet
        (CONFIG.feed_stale_after + 10, "STALE"),  # no proven event for >30s
        (CONFIG.feed_offline_after + 10, "OFFLINE"),
    ],
)
def test_feed_freshness_is_tiered_not_binary(monkeypatch, tmp_path, age, expected):
    comps = _components(monkeypatch, tmp_path, age)
    if expected is None:
        # Within the proof window the cross-check must not overwrite anything.
        assert comps["binance_spot"]["state"] not in {"DEGRADED", "STALE"}
        return
    assert comps["binance_spot"]["state"] == expected


def test_a_late_feed_is_not_reported_as_a_dead_socket(monkeypatch, tmp_path):
    """The exact incident signature: 6s late must not read the same as OFFLINE."""
    late = _components(monkeypatch, tmp_path, 6.0)["binance_spot"]
    dead = _components(monkeypatch, tmp_path, 10_000.0)["binance_spot"]
    assert late["state"] != dead["state"]
    assert dead["state"] == "OFFLINE"


def test_supervisor_diagnostics_survive_the_cross_check(monkeypatch, tmp_path):
    """reconnect_count / last_error / last_event_at are the evidence that
    distinguishes 'reconnecting' from 'never connected'. Overriding the state
    must not erase them."""
    supervisor = {
        "key": "binance_spot",
        "state": "RECONNECTING",
        "last_event_at": "2026-09-21T16:00:00+00:00",
        "age_seconds": 40.0,
        "reconnect_count": 7,
        "last_error": "ConnectionClosedError",
        "recovery_level": 2,
        "detail": "backing off",
    }
    comp = _components(monkeypatch, tmp_path, 40.0, supervisor_component=supervisor)["binance_spot"]
    assert comp["state"] == "STALE"
    assert comp["reconnect_count"] == 7
    assert comp["last_error"] == "ConnectionClosedError"
    assert comp["last_event_at"] == "2026-09-21T16:00:00+00:00"
    assert comp["recovery_level"] == 2


def test_missing_marker_is_still_offline(monkeypatch, tmp_path):
    """Absent proof is not the same as proof of freshness."""
    comps = _components(monkeypatch, tmp_path, 1.0, markers={})
    assert comps["binance_spot"]["state"] == "OFFLINE"
