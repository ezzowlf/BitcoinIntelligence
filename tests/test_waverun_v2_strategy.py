import sqlite3

from bitcoin_cycle_analyzer.short_term.waverun_v2 import (
    FindingsStore,
    enforce_magnitude_monotonicity,
    pareto_frontier,
    prefreeze_gate,
)


def test_magnitude_probabilities_are_non_increasing():
    assert enforce_magnitude_monotonicity([0.8, 0.7, 0.75, 0.4]) == [0.8, 0.7, 0.7, 0.4]


def test_prefreeze_gate_requires_every_scientific_condition():
    passing = {"precision": 0.71, "net_ev": 1, "signals_per_day": 3, "signals": 100, "positive_folds": 3, "folds": 4, "parameter_cliff": False}
    assert prefreeze_gate(passing)["passed"] is True
    assert prefreeze_gate({**passing, "signals_per_day": 2.99})["passed"] is False


def test_pareto_removes_dominated_configuration():
    rows = [{"id": "a", "precision": 0.7, "signals_per_day": 3, "net_ev": 1}, {"id": "b", "precision": 0.6, "signals_per_day": 2, "net_ev": 0}]
    assert [row["id"] for row in pareto_frontier(rows)] == ["a"]


def test_findings_store_is_append_only(tmp_path):
    store = FindingsStore(tmp_path / "findings.sqlite")
    row = {"category": "TEST", "statement": "fact", "evidence": {}, "period": "p", "sample_size": 1, "confidence": "LOW", "supports": "", "contradicts": "", "status": "OBSERVED", "created_at": "2026-01-01T00:00:00Z"}
    finding_id = store.append(row)
    assert store.append({**row, "created_at": "2026-02-01T00:00:00Z"}) == finding_id
    assert len(store.rows()) == 1
    with sqlite3.connect(store.path) as database:
        try:
            database.execute("DELETE FROM findings WHERE finding_id=?", (finding_id,))
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("findings must be append-only")
