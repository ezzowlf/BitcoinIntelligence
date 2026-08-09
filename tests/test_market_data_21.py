from __future__ import annotations
import pandas as pd

from bitcoin_cycle_analyzer.data_contracts import MarketDataRecord, provider_disagreement, point_in_time
from bitcoin_cycle_analyzer.derivatives.funding import analyze_funding
from bitcoin_cycle_analyzer.derivatives.open_interest import analyze_open_interest
from bitcoin_cycle_analyzer.derivatives.engine import analyze_derivatives
from bitcoin_cycle_analyzer.episodes import cluster_episodes
from bitcoin_cycle_analyzer.entry_timing import entry_timing_state
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.news.event_model import decay_weight, EventCategory, NewsEvent, EventDirection
from bitcoin_cycle_analyzer.onchain import StoreOnChainProvider
from bitcoin_cycle_analyzer.derivatives.providers import BinanceFuturesProvider
from bitcoin_cycle_analyzer.scoring import confluence_score, factor_evidence


def frame(values, start="2024-01-01", freq="8h"):
    events = pd.date_range(start, periods=len(values), freq=freq, tz="UTC")
    return pd.DataFrame({"value": values, "event_timestamp": events,
                         "available_at": events + pd.Timedelta(milliseconds=1), "provider": "test"})


def test_point_in_time_excludes_future_release():
    data = frame([1, 2])
    assert len(point_in_time(data, data.available_at.iloc[0])) == 1


def test_provider_disagreement_reduces_confidence():
    t = pd.Timestamp("2024-01-01", tz="UTC")
    records = [MarketDataRecord("x", value, t, t, t, provider, provider, "HIGH")
               for value, provider in [(100, "a"), (120, "b")]]
    assert provider_disagreement(records)["detected"] is True
    assert provider_disagreement(records)["confidence_multiplier"] == .5


def test_funding_regime_and_oi_changes():
    funding = analyze_funding(frame([-.001] * 20 + [.01]), pd.Timestamp("2025-01-01", tz="UTC"))
    assert funding["state"] == "OVERHEATED"
    assert funding["mean_7d"] is not None
    oi = analyze_open_interest(frame(range(1, 200), freq="1h"), pd.Timestamp("2025-01-01", tz="UTC"))
    assert oi["change_24h"] > 0 and oi["change_1h"] > 0
    combined = analyze_derivatives(pd.Timestamp("2025-01-01", tz="UTC"), frame([-.001] * 20 + [.01]), frame(range(1, 200), freq="1h"))
    assert combined["risk_score"] >= 70


def test_external_store_enforces_available_at(tmp_path):
    store = ExternalMetricStore(tmp_path / "external.db")
    event = pd.Timestamp("2024-01-01", tz="UTC")
    available = event + pd.Timedelta(days=2)
    store.upsert([MarketDataRecord("mvrv", 2.0, event, available, available, "cm", "id", "LOW")])
    assert store.load("mvrv", event).empty
    assert StoreOnChainProvider(store).latest("mvrv", available).value == 2.0


def test_timestamp_normalization_accepts_aware_values():
    assert BinanceFuturesProvider._utc(pd.Timestamp("2024-01-01", tz="UTC")).tzname() == "UTC"


def test_episode_clustering_and_entry_execution_disabled():
    events = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    clusters = cluster_episodes(pd.DataFrame({"timestamp": events, "signal": [1, 1, 0, 1, 1]}), min_gap_days=5)
    assert clusters.episode_id.nunique() == 1
    assert entry_timing_state("bullish", "HIGH", 50)["execution"] == "DISABLED"


def test_news_decay_is_category_specific_and_causal():
    now = pd.Timestamp("2024-01-03", tz="UTC")
    past = NewsEvent(now - pd.Timedelta(days=1), now - pd.Timedelta(days=1), EventCategory.GEOPOLITICAL, "x", .8, EventDirection.RISK_OFF, .9, "test")
    future = NewsEvent(now + pd.Timedelta(days=1), now + pd.Timedelta(days=1), EventCategory.GEOPOLITICAL, "x", .8, EventDirection.RISK_OFF, .9, "test")
    assert decay_weight(past, now) > 0
    assert decay_weight(future, now) == 0


def test_confluence_deduplicates_source_event_and_evidence_uses_oos():
    result = confluence_score([
        {"name": "a", "group": "g1", "strength": .8, "source_id": "s", "event_id": "e"},
        {"name": "b", "group": "g2", "strength": .8, "source_id": "s", "event_id": "e"},
    ])
    assert result["independent_groups"] == 1
    rejected = factor_evidence(100, 1, 1, 1, 1, -.1, .2)
    assert rejected["status"] == "REJECTED"
