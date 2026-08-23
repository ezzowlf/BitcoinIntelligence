from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_waverun_v5_3_clean_fast_entry_forensics.py"
)
SPEC = importlib.util.spec_from_file_location("clean_fast_forensics", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_trend_efficiency_is_causal_and_deterministic() -> None:
    assert MODULE.efficiency(np.array([10.0, 9.0, 8.0])) == 1.0
    assert MODULE.efficiency(np.array([10.0, 9.0, 10.0])) == 0.0


def test_veto_application_blocks_only_declared_side() -> None:
    frame = pd.DataFrame({"spot_pressure_10s": [-0.2, 0.1, 0.2]})
    rule = {
        "feature": "spot_pressure_10s",
        "block_operator": ">",
        "threshold": 0.15,
    }
    assert MODULE.applies(frame, rule).tolist() == [True, True, False]


def test_expansion_phase_has_fixed_boundaries() -> None:
    assert MODULE.expansion_phase(10, 0.0) == "COMPRESSION"
    assert MODULE.expansion_phase(30, 0.0) == "PRE_EXPANSION"
    assert MODULE.expansion_phase(60, 0.0) == "EARLY_EXPANSION"
    assert MODULE.expansion_phase(80, 0.0) == "MATURE_EXPANSION"
    assert MODULE.expansion_phase(80, 1.0) == "EXHAUSTION"
