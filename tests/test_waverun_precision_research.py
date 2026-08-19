import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_waverun_precision_research import _ece, _matrices, _ranking_cell, _targets


def outcome_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "gross_return_300s_d3": [0.01, -0.01, np.nan],
        "long_net_300s_d3": [0.005, -0.02, np.nan],
        "short_net_300s_d3": [-0.02, 0.005, np.nan],
    })


def test_cost_aware_targets_separate_move_and_direction():
    direction, move, long_net, short_net, valid = _targets(outcome_frame(), 300, 3)
    assert direction.tolist() == [1, 0, 0]
    assert move.tolist() == [1, 1, 0]
    assert long_net[0] < 0.005 and short_net[1] < 0.005
    assert valid.tolist() == [True, True, False]


def test_matrices_use_train_statistics_and_remove_nonfinite_values():
    train = pd.DataFrame({"x": [1.0, 2.0, np.nan], "y": [2.0, 2.0, 2.0]})
    validation = pd.DataFrame({"x": [100.0, np.inf], "y": [2.0, 2.0]})
    train_x, validation_x = _matrices([train, validation], ["x", "y"])
    assert np.isfinite(train_x).all() and np.isfinite(validation_x).all()
    assert validation_x[0, 0] > 10


def test_ranking_requires_positive_cost_adjusted_ev_and_samples():
    result = {"coverage_curve": [
        {"signals": 99, "precision": 0.9, "net_ev": 0.01, "coverage": 0.01},
        {"signals": 100, "precision": 0.7, "net_ev": -0.01, "coverage": 0.02},
    ]}
    assert _ranking_cell(result)["signals"] == 0


def test_ece_is_zero_for_matching_bins():
    assert _ece(np.array([0.0, 1.0]), np.array([0, 1])) == 0
