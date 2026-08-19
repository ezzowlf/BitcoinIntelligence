from datetime import date

import numpy as np
import pytest

from bitcoin_cycle_analyzer.short_term.research_protocol import (
    CandidateFreeze,
    ExperimentRegistry,
    HoldoutLockedError,
    assert_days_allowed,
    selective_metrics,
    wilson_interval,
)


def test_holdout_requires_frozen_candidate():
    with pytest.raises(HoldoutLockedError):
        assert_days_allowed([date(2026, 8, 16)])
    assert_days_allowed([date(2026, 8, 16)], {"candidate_frozen": True})


def test_candidate_freeze_is_stable_and_execution_disabled():
    candidate = CandidateFreeze("logistic", 180, ("price", "flow"), {"c": 1}, 0.8, {"reaction": 3}, {}, "2026-01-01T00:00:00Z")
    assert candidate.fingerprint() == candidate.fingerprint()
    assert candidate.to_manifest()["execution"] == "DISABLED"


def test_wilson_interval_and_sample_guard():
    low, high = wilson_interval(80, 100)
    assert low < 0.8 < high
    with pytest.raises(ValueError):
        wilson_interval(2, 1)


def test_precision_coverage_is_monotonic_in_signal_count():
    confidence = np.linspace(0, 1, 100)
    correct = confidence >= 0.5
    metrics = selective_metrics(confidence, correct, np.ones(100) * 0.001)
    assert [row["signals"] for row in metrics] == sorted((row["signals"] for row in metrics), reverse=True)
    assert metrics[-1]["precision"] == 1


def test_registry_is_append_only_and_counts_variants(tmp_path):
    registry = ExperimentRegistry(tmp_path / "registry.jsonl")
    registry.append({"model": "logistic", "feature_groups": ["price"], "threshold": 0.7, "strategy": "direction"})
    registry.append({"model": "forest", "feature_groups": ["price", "flow"], "threshold": 0.8, "strategy": "direction"})
    assert registry.counts() == {"experiments": 2, "models": 2, "feature_sets": 2, "thresholds": 2, "strategy_candidates": 1}
