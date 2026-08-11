import tempfile
from pathlib import Path

import pandas as pd
import pytest

from bitcoin_cycle_analyzer.event_evidence import PointInTimeEventDatabase, EVENT_IMPORTANCE, EVENT_STATUS, CAUSALITY_LEVELS
from bitcoin_cycle_analyzer.event_intelligence import classify_causality, expected_vs_observed, dedupe_candidates, event_evidence_family


@pytest.fixture
def temp_db(tmp_path):
    return PointInTimeEventDatabase(tmp_path / "events.db")


VALID_EVENT = {
    "event_time": "2024-01-10T21:00:00Z", "first_known_at": "2024-01-10T21:00:00Z", "available_at": "2024-01-10T21:00:00Z",
    "source_url": "https://www.sec.gov/example", "source_name": "US SEC", "source_quality": "PRIMARY",
    "category": "ETF", "headline": "Test event", "importance": "CRITICAL", "status": "OFFICIAL", "expected_direction": "BULLISH",
}


# ---------------------------------------------------------------- Schema

def test_event_schema_accepts_all_new_fields(temp_db):
    eid = temp_db.append(VALID_EVENT)
    row = temp_db.as_of(pd.Timestamp.now(tz="UTC"))
    assert row.iloc[0]["importance"] == "CRITICAL"
    assert row.iloc[0]["status"] == "OFFICIAL"
    assert row.iloc[0]["expected_direction"] == "BULLISH"


def test_invalid_importance_is_rejected(temp_db):
    with pytest.raises(ValueError):
        temp_db.append({**VALID_EVENT, "importance": "SUPER_HIGH"})


def test_invalid_status_is_rejected(temp_db):
    with pytest.raises(ValueError):
        temp_db.append({**VALID_EVENT, "status": "MAYBE"})


def test_unsourced_https_url_is_rejected(temp_db):
    with pytest.raises(ValueError):
        temp_db.append({**VALID_EVENT, "source_url": "http://not-https.example"})


def test_migration_is_backward_compatible_with_pre_existing_rows(tmp_path):
    # Simulate a pre-Auftrag-3 database (no new columns) by inserting via raw SQL,
    # then confirm PointInTimeEventDatabase still opens and migrates it cleanly.
    import sqlite3
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE historical_events(event_id TEXT PRIMARY KEY,event_time TEXT NOT NULL,first_known_at TEXT NOT NULL,available_at TEXT NOT NULL,source_url TEXT NOT NULL,source_name TEXT NOT NULL,source_quality TEXT NOT NULL,category TEXT NOT NULL,headline TEXT NOT NULL,severity_at_time TEXT,severity_ex_post TEXT,created_at TEXT DEFAULT CURRENT_TIMESTAMP)")
        db.execute("INSERT INTO historical_events VALUES('x','2020-01-01','2020-01-01','2020-01-01','https://example.com','Example','PRIMARY','MACRO','legacy row',NULL,NULL,CURRENT_TIMESTAMP)")
    reopened = PointInTimeEventDatabase(path)
    rows = reopened.as_of(pd.Timestamp.now(tz="UTC"))
    assert len(rows) == 1
    assert pd.isna(rows.iloc[0]["importance"])  # NULL, never guessed/backfilled


# ---------------------------------------------------------------- Append-only / PIT (pre-existing, re-verified under new schema)

def test_append_only_trigger_still_blocks_update_after_migration(temp_db):
    import sqlite3
    temp_db.append(VALID_EVENT)
    with pytest.raises(sqlite3.IntegrityError):
        with sqlite3.connect(temp_db.path) as db:
            db.execute("UPDATE historical_events SET importance='LOW'")


def test_pit_ordering_still_enforced(temp_db):
    with pytest.raises(ValueError):
        temp_db.append({**VALID_EVENT, "available_at": "2024-01-09T00:00:00Z"})  # before event_time


def test_event_not_visible_before_available_at(temp_db):
    temp_db.append(VALID_EVENT)
    before = temp_db.as_of(pd.Timestamp("2024-01-10T20:00:00Z"))
    after = temp_db.as_of(pd.Timestamp("2024-01-10T22:00:00Z"))
    assert before.empty
    assert len(after) == 1


# ---------------------------------------------------------------- Causality guard

def test_causality_levels_are_the_canonical_set():
    assert set(CAUSALITY_LEVELS) == {"UNKNOWN", "TEMPORAL_ASSOCIATION", "PLAUSIBLE_CONTRIBUTOR", "MULTIPLE_PLAUSIBLE_CONTRIBUTORS", "STRONG_EVIDENCE"}


def test_classify_causality_never_returns_certainty_without_confirmed_mechanism():
    result = classify_causality(n_plausible_contributors=1, has_strong_temporal_link=True, has_confirmed_mechanism=False)
    assert result["causality_level"] != "STRONG_EVIDENCE"


def test_classify_causality_note_always_present():
    for n in range(4):
        result = classify_causality(n, True, False)
        assert "not proof" in result["note"].lower() or "certainty" in result["note"].lower()


# ---------------------------------------------------------------- Expected vs observed

def test_expected_vs_observed_flags_mismatch():
    result = expected_vs_observed("BULLISH", -0.03)
    assert result["comparison"] == "MISMATCH"


def test_expected_vs_observed_flags_match():
    result = expected_vs_observed("BEARISH", -0.02)
    assert result["comparison"] == "MATCH"


def test_expected_vs_observed_handles_missing_data_honestly():
    result = expected_vs_observed(None, None)
    assert result["comparison"] == "UNAVAILABLE"


def test_expected_vs_observed_rejects_invalid_direction():
    with pytest.raises(ValueError):
        expected_vs_observed("VERY_BULLISH", 0.01)


# ---------------------------------------------------------------- Dedup

def test_dedupe_clusters_near_duplicate_same_time_headlines():
    candidates = [
        {"headline": "SEC approves spot Bitcoin ETF", "event_time": "2024-01-10T21:00:00Z"},
        {"headline": "SEC approves spot Bitcoin ETFs for listing", "event_time": "2024-01-10T21:03:00Z"},
        {"headline": "Fed cuts rates by 50bps", "event_time": "2020-03-03T15:00:00Z"},
    ]
    clusters = dedupe_candidates(candidates)
    assert len(clusters) == 2
    assert any(len(c) == 2 for c in clusters)


def test_dedupe_does_not_merge_similar_text_far_apart_in_time():
    candidates = [
        {"headline": "Bitcoin ETF sees record inflows", "event_time": "2024-01-01T00:00:00Z"},
        {"headline": "Bitcoin ETF sees record inflows", "event_time": "2024-06-01T00:00:00Z"},
    ]
    clusters = dedupe_candidates(candidates)
    assert len(clusters) == 2  # same text, 5 months apart -> genuinely different occurrences


def test_dedupe_empty_input():
    assert dedupe_candidates([]) == []


# ---------------------------------------------------------------- Event evidence family (informative-only)

def test_event_evidence_family_shape_matches_other_families():
    empty = pd.DataFrame()
    result = event_evidence_family(empty)
    for key in ("family", "direction", "strength", "facts", "provenance"):
        assert key in result
    assert result["family"] == "EVENT_CONTEXT"


def test_event_evidence_family_is_never_wired_into_decision_gates():
    # Structural guard: EVENT_CONTEXT must not appear inside decision_intelligence's
    # own evidence family list — it stays a separate, informative-only surface.
    from bitcoin_cycle_analyzer.decision_intelligence import EVIDENCE_FAMILIES
    assert "EVENT_CONTEXT" not in EVIDENCE_FAMILIES


def test_event_evidence_family_declares_zero_decision_weight():
    result = event_evidence_family(pd.DataFrame())
    assert "NONE" in result["decision_weight"]


# ---------------------------------------------------------------- Golden dataset / seed script

def test_golden_halving_events_seed_is_idempotent_and_sourced(tmp_path):
    from scripts.seed_golden_events import seed, GOLDEN_HALVING_EVENTS
    path = tmp_path / "seed_test.db"
    first = seed(path)
    second = seed(path)  # re-running must not create duplicates (INSERT OR IGNORE)
    assert len(first) == len(GOLDEN_HALVING_EVENTS)
    db = PointInTimeEventDatabase(path)
    assert db.health()["events"] == len(GOLDEN_HALVING_EVENTS)
    for event in GOLDEN_HALVING_EVENTS:
        assert event["category"] == "HALVING"
        assert event["importance"] in EVENT_IMPORTANCE
        assert event["status"] in EVENT_STATUS


def test_real_database_has_golden_halving_events():
    root = Path(__file__).resolve().parents[1]
    db = PointInTimeEventDatabase(root / "database" / "historical_event_evidence.db")
    rows = db.as_of(pd.Timestamp.now(tz="UTC"))
    halvings = rows[rows.category == "HALVING"]
    assert len(halvings) == 4


# ---------------------------------------------------------------- Serialization

def test_causality_and_expected_vs_observed_results_are_json_serializable():
    import json
    json.dumps(classify_causality(2, True, False))
    json.dumps(expected_vs_observed("BULLISH", 0.01))
    json.dumps(event_evidence_family(pd.DataFrame()))
