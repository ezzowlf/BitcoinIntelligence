import pandas as pd
import pytest
from bitcoin_cycle_analyzer.data_provider import OHLCVStore, validate_ohlcv, resample, ProviderError, KrakenProvider
from bitcoin_cycle_analyzer.indicators import add_indicators
from bitcoin_cycle_analyzer.swing_detection import detect_swings, swings_as_of
from bitcoin_cycle_analyzer.fibonacci import levels, confluence_zones
from bitcoin_cycle_analyzer.elliott_wave import analyze_scenarios

def test_data_import_and_incremental_store(tmp_path, ohlcv):
    store = OHLCVStore(tmp_path / "x.db")
    assert store.upsert("1d", ohlcv.iloc[:10]) == 10
    store.upsert("1d", ohlcv.iloc[5:15])
    assert len(store.load("1d")) == 15
    assert store.latest("1d") == ohlcv.index[14]

def test_missing_and_invalid_data(ohlcv):
    with pytest.raises(ValueError): validate_ohlcv(ohlcv.drop(columns="volume"))
    broken = ohlcv.copy(); broken.iloc[0, broken.columns.get_loc("high")] = 0
    with pytest.raises(ValueError): validate_ohlcv(broken)

def test_indicators_and_resample(ohlcv):
    enriched = add_indicators(ohlcv)
    assert enriched.ema_200.iloc[-1] > 0
    assert 0 <= enriched.rsi_14.iloc[-1] <= 100
    assert len(resample(ohlcv, "1w")) < len(ohlcv)

def test_swings_are_known_only_after_confirmation(ohlcv):
    swings = detect_swings(add_indicators(ohlcv), window=5)
    assert (swings.confirmed_at > swings.pivot_time).all()
    cutoff = swings.confirmed_at.iloc[2]
    assert (swings_as_of(swings, cutoff).confirmed_at <= cutoff).all()

def test_fibonacci_and_confluence():
    result = levels(100, 200)
    assert next(x.price for x in result if x.ratio == .5) == 150
    zones = confluence_zones(result + levels(99, 201), tolerance_pct=.02)
    assert zones and zones[0]["count"] >= 2

def test_elliott_is_probabilistic(ohlcv):
    scenarios = analyze_scenarios(detect_swings(add_indicators(ohlcv), window=5))
    assert round(sum(x["confidence"] for x in scenarios), 1) == 100
    assert all(x["invalidation"] for x in scenarios)

def test_api_failure(monkeypatch):
    def fail(*args, **kwargs): raise RuntimeError("offline")
    monkeypatch.setattr("requests.get", fail)
    with pytest.raises(RuntimeError): KrakenProvider().fetch("1d")

