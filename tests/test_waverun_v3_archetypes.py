import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_waverun_v3_archetype_research.py"
SPEC = importlib.util.spec_from_file_location("waverun_v3", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
v3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v3)


def trajectory(value=1.0):
    return {offset: {feature: value for feature in v3.FEATURES} for offset in v3.OFFSETS}


def test_causal_vector_uses_only_declared_past_and_t0_offsets():
    vector = v3.causal_vector(trajectory())
    assert len(vector) == len(v3.FEATURES) * 4
    assert not any(offset.startswith("T+") for offset in v3.OFFSETS)


def test_trajectory_slope_and_acceleration_are_order_sensitive():
    item = trajectory(0.0)
    feature = v3.FEATURES[0]
    item["T-30s"][feature], item["T-10s"][feature], item["T0"][feature] = 1, 2, 4
    level, slope, acceleration, _ = v3.causal_vector(item)[:4]
    assert (level, slope, acceleration) == (4, 3, 1)


def test_imputation_is_fit_from_discovery_only():
    train = np.array([[1.0, np.nan], [3.0, 5.0]])
    later = np.array([[np.nan, 999.0]])
    _, filled = v3.impute(train, later)
    assert filled[0, 0] == 2.0


def test_required_missing_offsets_are_explicit_not_fabricated():
    assert "T-600s" in v3.REQUIRED_OFFSETS
    assert "T-600s" not in v3.OFFSETS


def test_parameter_cliff_detection_is_bounded():
    assert v3.parameter_cliff([0.70, 0.69, 0.68]) is False
    assert v3.parameter_cliff([0.70, 0.40]) is True


def test_calibration_metrics_are_exact_for_perfect_probabilities():
    metrics = v3.calibration_metrics(np.array([0.0, 1.0]), np.array([0, 1]))
    assert metrics == {"brier": 0.0, "ece": 0.0}


def test_experiment_budget_blocks_unbounded_search():
    v3.enforce_experiment_budget(20)
    try:
        v3.enforce_experiment_budget(21)
    except RuntimeError:
        pass
    else:
        raise AssertionError("budget must be enforced")
