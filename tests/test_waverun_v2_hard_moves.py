import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_waverun_v2_hard_move_research.py"
SPEC = importlib.util.spec_from_file_location("waverun_v2_hard", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
hard = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(hard)


def test_hard_target_grid_is_frozen_and_economic():
    assert hard.TARGETS_USD == (200, 300, 400, 500, 600, 800)
    assert hard.ADVERSE_USD == (50, 75, 100, 150, 200)
    assert hard.HORIZONS == (30, 60, 90, 180, 300, 600)


def test_target_must_arrive_before_adverse_barrier():
    success = hard.barrier_result(np.array([1000, 950, 1200]), 1, 200, 75)
    failure = hard.barrier_result(np.array([1000, 900, 1250]), 1, 200, 75)
    assert success["success"] is True
    assert failure["success"] is False


def test_short_barrier_path_is_direction_normalized():
    result = hard.barrier_result(np.array([1000, 1020, 790]), -1, 200, 50)
    assert result["success"] is True
    assert result["target_time_seconds"] == 10


def test_move_library_does_not_recount_one_continuous_move():
    import pandas as pd

    rows = 250
    frame = pd.DataFrame({name: np.zeros(rows) for name in hard.SNAPSHOT_COLUMNS if name not in {"regime", "origin"}})
    frame["timestamp"] = pd.date_range("2025-01-01", periods=rows, freq="5s", tz="UTC")
    frame["mid"] = 1000 + np.arange(rows) * 5
    frame["regime"] = "RANGE"
    frame["origin"] = "UNKNOWN"
    assert len(hard.independent_moves(frame, "TEST")) == 2
