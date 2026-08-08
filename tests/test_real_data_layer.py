import pandas as pd
from bitcoin_cycle_analyzer.data_provider import BitstampProvider, OHLCVStore, resample
from bitcoin_cycle_analyzer.data_quality import quality_report


def test_canonical_metadata_and_unique_timestamps(tmp_path, ohlcv):
    store = OHLCVStore(tmp_path / "canonical.db")
    store.upsert("1d", ohlcv.iloc[:5], provider="test", source="fixture", data_version="v1")
    store.upsert("1d", ohlcv.iloc[3:7], provider="test", source="fixture", data_version="v1")
    loaded = store.load_canonical("1d")
    assert len(loaded) == 7
    assert loaded.index.is_unique and loaded.index.is_monotonic_increasing
    assert set(["source", "provider", "import_timestamp", "data_version"]) <= set(loaded.columns)


def test_quality_report_detects_without_repairing(ohlcv):
    broken = ohlcv.iloc[:20].drop(ohlcv.index[5]).copy()
    broken.loc[broken.index[3], "open"] = broken.loc[broken.index[3], "high"] * 2
    report = quality_report(broken, "1d")
    assert report["critical_issue_count"] == 1
    assert len(report["issues"]["missing_periods"]) == 1
    assert report["repairs_applied"] == []


def test_weekly_monthly_use_only_completed_source_bars(ohlcv):
    cutoff = ohlcv.index[100]
    weekly_before = resample(ohlcv.loc[:cutoff], "1w")
    monthly_before = resample(ohlcv.loc[:cutoff], "1M")
    mutated = ohlcv.copy()
    mutated.loc[mutated.index > cutoff, ["open", "high", "low", "close"]] *= 100
    pd.testing.assert_frame_equal(weekly_before, resample(mutated.loc[:cutoff], "1w"))
    pd.testing.assert_frame_equal(monthly_before, resample(mutated.loc[:cutoff], "1M"))
    assert weekly_before.index.max() <= cutoff
    assert monthly_before.index.max() <= cutoff


def test_bitstamp_payload_parsing(monkeypatch):
    calls = {"count": 0}
    class Response:
        def raise_for_status(self): pass
        def json(self):
            calls["count"] += 1
            rows = [{"timestamp": str(int(pd.Timestamp("2026-08-08", tz="UTC").timestamp())), "open": "10", "high": "12", "low": "9", "close": "11", "volume": "2"}] if calls["count"] == 1 else []
            return {"data": {"ohlc": rows}}
    monkeypatch.setattr("requests.get", lambda *a, **k: Response())
    provider = BitstampProvider()
    frame = provider.fetch("1d", pd.Timestamp("2026-08-08", tz="UTC"))
    assert list(frame.columns) == ["open", "high", "low", "close", "volume"]
    assert frame.index.tz is not None
