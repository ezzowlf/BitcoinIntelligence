from datetime import date

import pytest

from bitcoin_cycle_analyzer.waverun_v5 import (
    BarrierTarget,
    HoldoutLockedError,
    assert_holdout_locked,
    gate,
)


def test_barrier_grid_is_explicit():
    assert BarrierTarget(300, 75, 180).magnitude_usd == 300
    with pytest.raises(ValueError):
        BarrierTarget(125, 75, 180)


def test_final_holdout_is_locked_until_freeze():
    with pytest.raises(HoldoutLockedError):
        assert_holdout_locked([date(2026, 8, 16)])
    assert_holdout_locked([date(2026, 8, 16)], candidate_frozen=True)


def test_gate_does_not_claim_without_all_evidence():
    result = gate({"signals_per_day": 3, "precision": .70, "net_ev": 1, "N": 100,
                   "positive_folds": 1, "folds": 3, "calibrated": True,
                   "parameter_cliff": False})
    assert result["passed"] is False
    assert result["execution"] == "DISABLED"
