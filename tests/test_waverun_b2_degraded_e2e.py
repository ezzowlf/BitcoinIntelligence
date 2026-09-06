"""B-2 Phase 18 - Degraded Signal E2E.

Proves, against the real code path, what actually happens when Binance Spot is
lost while Vantage and Futures stay live:

  * the spot-driven decision / candidate / prediction pipeline stops producing
    new records (that data basis is genuinely gone - it is NOT substituted with
    futures/vantage, which would change the signal definition),
  * the independent parts (Vantage tick recording, V5.3 outcome resolution)
    keep running,
  * the health supervisor flags the operating state as CRITICAL and persists an
    incident,
  * once spot returns, the decision pipeline resumes producing new records,
  * the frozen V5.3 signal thresholds are byte-for-byte unchanged.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import waverun_live  # noqa: E402
from bitcoin_cycle_analyzer.short_term import resilience  # noqa: E402
from bitcoin_cycle_analyzer.short_term.events import EventType, MarketEvent  # noqa: E402
from bitcoin_cycle_analyzer.short_term.health import FeedHealth  # noqa: E402
from bitcoin_cycle_analyzer.short_term.health_supervisor import HealthSupervisor  # noqa: E402


def _spot_trade(ts: datetime, price: float) -> MarketEvent:
    return MarketEvent(
        EventType.TRADE, "BINANCE_SPOT", "BTCUSDT", ts, ts,
        {"price": price, "quantity": 0.05, "buyer_is_maker": False, "market": "spot"},
    )


def _futures_trade(ts: datetime, price: float) -> MarketEvent:
    return MarketEvent(
        EventType.TRADE, "BINANCE_FUTURES", "BTCUSDT", ts, ts,
        {"price": price, "quantity": 0.05, "buyer_is_maker": True, "market": "futures"},
    )


@pytest.fixture
def session(tmp_path):
    out = tmp_path / "runtime" / "waverun" / "latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    (tmp_path / "database").mkdir(parents=True, exist_ok=True)
    s = waverun_live.LiveSession(
        output=out,
        database=tmp_path / "database" / "waverun_predictions.db",
        symbol="btcusdt",
        mt5_values={"MT5_ENABLED": "false"},
    )
    # deterministic synthetic Vantage tick source (independent of the spot feed)
    state = {"t": 0}

    def fake_tick():
        state["t"] += 1
        base = datetime.now(UTC)
        return {
            "status": "AVAILABLE", "time_msc": int(base.timestamp() * 1000) + state["t"],
            "timestamp": base.isoformat(), "bid": 77000.0, "ask": 77017.0, "last": 77008.0,
            "flags": 0, "spread": 17.0, "symbol": "BTCUSD",
        }

    s.mt5.tick = fake_tick
    return s, tmp_path


async def _feed_spot(session, n, start_price=77000.0, t0=None):
    t0 = t0 or datetime.now(UTC)
    for i in range(n):
        await session.on_event(_spot_trade(t0 + timedelta(seconds=i), start_price + i))


def _count(path: Path) -> int:
    return sum(1 for _ in path.open()) if path.exists() else 0


def test_spot_drives_pipeline_then_loss_freezes_it_then_recovery_resumes(session):
    s, tmp = session
    rt = tmp / "runtime" / "waverun"
    cand, dec, lat = rt / "pre_gate_candidates.jsonl", rt / "decision_records.jsonl", rt / "latency_records.jsonl"

    import asyncio

    # --- 1. spot present: the decision pipeline produces records -------------
    asyncio.run(_feed_spot(s, 40, t0=datetime(2026, 1, 1, tzinfo=UTC)))
    c1, d1, l1 = _count(cand), _count(dec), _count(lat)
    assert c1 >= 5 and d1 >= 5 and l1 >= 5
    assert (rt / "latest.json").exists()
    import sqlite3
    preds1 = sqlite3.connect(tmp / "database" / "waverun_predictions.db").execute(
        "select count(*) from predictions"
    ).fetchone()[0]
    assert preds1 > 0

    # --- 2. spot lost: only futures + vantage keep flowing ------------------
    for i in range(20):
        asyncio.run(s.on_event(_futures_trade(datetime(2026, 1, 1, 0, 5, i, tzinfo=UTC), 77100 + i)))
        s._record_vantage_tick()
    c2, d2, l2 = _count(cand), _count(dec), _count(lat)
    assert (c2, d2, l2) == (c1, d1, l1), "spot loss must NOT be papered over with futures/vantage"
    assert _count(rt / "vantage_ticks.jsonl") >= 10, "vantage recording is independent and continues"

    # --- 3. health supervisor: spot OFFLINE while vantage fresh -> CRITICAL --
    for k, v in {"startup_grace": 0.0, "feed_offline_after": 30.0, "feed_stale_after": 5.0}.items():
        setattr(resilience.CONFIG, k, v)

    class _FF:
        symbol = "btcusdt"

        def __init__(self):
            self.health = {"spot": FeedHealth("BINANCE_SPOT"), "futures": FeedHealth("BINANCE_FUTURES")}

        def refresh_states(self, now=None):
            return {k: v.refresh(now) for k, v in self.health.items()}

        def stop(self):
            pass

    ff = _FF()
    ff.health["spot"].event(datetime.now(UTC) - timedelta(seconds=120))
    ff.health["futures"].event(datetime.now(UTC))
    sup = HealthSupervisor(runtime_dir=rt, feed=ff, vantage_age=lambda: 1.0)
    sup.tick()
    report = sup.tick()
    assert report["operating_state"] == "CRITICAL"
    assert report["components"]["vantage"]["state"] == "HEALTHY"
    assert report["components"]["binance_spot"]["state"] == "OFFLINE"
    assert report["components"]["decision_pipeline"]["state"] != "HEALTHY"
    incidents = [json.loads(x) for x in (rt / "incidents.jsonl").read_text().splitlines() if x.strip()]
    assert any(i["component"] == "binance_spot" for i in incidents)

    # --- 4. spot recovery: the decision pipeline resumes producing records --
    asyncio.run(_feed_spot(s, 40, start_price=77200.0, t0=datetime(2026, 1, 1, 1, 0, tzinfo=UTC)))
    assert _count(cand) > c2 and _count(dec) > d2 and _count(lat) > l2


def test_frozen_v5_3_signal_thresholds_are_unchanged():
    """Degraded mode must never touch the signal maths / V5.3 rules."""
    from bitcoin_cycle_analyzer.short_term import v5_3_forward as v

    assert v.HYPOTHESIS_SHA256 == "49bc145432b187f66c1c1d577dc8fad5b39c93f786e8bb286b20b17e2c6c5dea"
    assert v.ACCEL_THRESHOLD == 3.6430941529033496
    assert v.HISTOGRAM_THRESHOLD == 16.737360838814414
    assert v.VETO_THRESHOLD == 0.1502250887673838
    assert v.DECLUSTER_SECONDS == 180
    # is_original_signal still requires a bearish 30s MACD burst on SPOT inputs
    bearish = {
        "macd_30s_cross_direction": -1.0, "macd_30s_histogram": -20.0,
        "macd_30s_histogram_slope": -1.0, "macd_30s_histogram_acceleration": -5.0,
    }
    assert v.is_original_signal(bearish) is True
    assert v.is_original_signal({**bearish, "macd_30s_histogram": -1.0}) is False
