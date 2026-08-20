import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_waverun_magnitude_analysis.py"
SPEC = importlib.util.spec_from_file_location("waverun_magnitude", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
magnitude = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(magnitude)


def test_required_horizons_and_magnitude_ladder_are_fixed():
    assert magnitude.HORIZONS == (30, 60, 90, 180, 300)
    assert magnitude.MAGNITUDES_BP == (1, 2, 5, 10, 15, 20, 30, 50)
    assert magnitude.COST_BP > 0


def test_first_crossing_uses_causal_path_order():
    path = np.array([0.0, -2.0, 1.0, 5.0])
    assert magnitude.first_crossing(path, 5, True) == 15
    assert magnitude.first_crossing(path, 2, False) == 5
    assert magnitude.first_crossing(path, 10, True) is None


def test_magnitude_class_is_absolute_bp_ladder():
    assert magnitude.magnitude_class(0.9) == "BELOW_1BP"
    assert magnitude.magnitude_class(17) == "GE_15BP"
    assert magnitude.magnitude_class(80) == "GE_50BP"
