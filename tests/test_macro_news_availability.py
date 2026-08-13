import pandas as pd
import pytest

from bitcoin_cycle_analyzer.macro import analyze_macro, load_macro_series
from bitcoin_cycle_analyzer.macro.store import MacroReleaseStore
from bitcoin_cycle_analyzer.macro.contracts import MacroObservation


# --- Macro ---------------------------------------------------------------

def test_analyze_macro_with_no_series_is_unavailable():
    result = analyze_macro({}, pd.Timestamp.now(tz="UTC"))
    assert result["status"] == "UNAVAILABLE"
    assert result["reason"] == "FRED_API_KEY_MISSING_OR_NO_RELEASES"


def test_analyze_macro_with_one_valid_series_is_available():
    now = pd.Timestamp.now(tz="UTC")
    dxy = pd.DataFrame({"available_at": [now - pd.Timedelta(days=30), now - pd.Timedelta(days=1)], "value": [100.0, 101.5]})
    result = analyze_macro({"dxy": dxy}, now)
    assert result["status"] == "AVAILABLE"
    assert result["metrics"]["dxy"]["status"] == "AVAILABLE"
    assert result["metrics"]["cpi"]["status"] == "UNAVAILABLE"  # untouched metric stays honest


def test_load_macro_series_without_api_key_returns_empty_when_no_cache(tmp_path):
    series = load_macro_series(None, tmp_path / "macro.db", pd.Timestamp.now(tz="UTC"))
    assert series == {}


def test_load_macro_series_reads_existing_cache_without_needing_a_key(tmp_path):
    db_path = tmp_path / "macro.db"
    store = MacroReleaseStore(db_path)
    now = pd.Timestamp.now(tz="UTC")
    store.upsert([MacroObservation("dxy", now - pd.Timedelta(days=10), now - pd.Timedelta(days=10), 101.2, now - pd.Timedelta(days=9), now - pd.Timedelta(days=9), "rev:1", "fred-alfred-api")])
    series = load_macro_series(None, db_path, now)
    assert "dxy" in series
    assert not series["dxy"].empty


def test_load_macro_series_provider_error_never_crashes(tmp_path, monkeypatch):
    from bitcoin_cycle_analyzer.macro import loader as loader_module

    class ExplodingProvider:
        def __init__(self, api_key):
            pass

        def fetch_macro_initial(self, series_id, metric):
            raise RuntimeError("network down")

    monkeypatch.setattr(loader_module, "FredVintageProvider", ExplodingProvider)
    series = load_macro_series("fake-key", tmp_path / "macro.db", pd.Timestamp.now(tz="UTC"))
    assert series == {}  # no cache, fetch failed for every series - honest empty result, no crash


# --- News / events ---------------------------------------------------------

def test_news_summary_available_when_event_database_has_records(tmp_path):
    from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase

    db = PointInTimeEventDatabase(tmp_path / "events.db")
    db.append({"event_time": "2024-04-20T00:09:00Z", "first_known_at": "2024-04-20T00:09:00Z", "available_at": "2024-04-20T00:09:00Z", "source_url": "https://example.test", "source_name": "test", "source_quality": "HIGH_QUALITY_SECONDARY", "category": "HALVING", "headline": "test halving"})
    health = db.health()
    assert health["status"] == "AVAILABLE"
    assert health["events"] == 1


def test_news_summary_unavailable_when_event_database_is_empty(tmp_path):
    """event_db.health() itself reports INSUFFICIENT_DATA for an empty database;
    dashboard/app.py normalizes that to the binary AVAILABLE/UNAVAILABLE convention
    the other data_status modules use before it reaches news_summary."""
    from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase

    db = PointInTimeEventDatabase(tmp_path / "empty_events.db")
    health = db.health()
    assert health["status"] == "INSUFFICIENT_DATA"
    assert health["events"] == 0
    news_status = "AVAILABLE" if health["status"] == "AVAILABLE" else "UNAVAILABLE"
    assert news_status == "UNAVAILABLE"
