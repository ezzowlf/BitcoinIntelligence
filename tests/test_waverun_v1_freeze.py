import importlib.util
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_waverun_v1_blind_validation.py"
SPEC = importlib.util.spec_from_file_location("waverun_v1", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
v1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v1)


def test_v1_identity_and_holdout_are_fixed():
    assert v1.CANDIDATE_ID == "Q1_2025_180S_CHALLENGER_V1"
    assert v1.HORIZON == 180
    assert v1.THRESHOLD == 0.55
    assert not any(day in v1.HOLDOUT for bounds in v1.PERIODS.values() for day in v1.q1.days(*bounds))


def test_direct_logistic_probability_is_bounded():
    state = {"coef": [[1.0, -1.0]], "intercept": [0.0], "classes": [0, 1]}
    values = v1.probability(pd.DataFrame([[0.0, 0.0], [10.0, -10.0]]).to_numpy(), state)
    assert values[0] == 0.5
    assert 0 < values[1] < 1


def test_freeze_fingerprint_detects_mutation():
    payload = {"candidate_id": v1.CANDIDATE_ID, "threshold": v1.THRESHOLD}
    fingerprint = v1.hashlib.sha256(v1.canonical(payload)).hexdigest()
    payload["threshold"] = 0.60
    assert v1.hashlib.sha256(v1.canonical(payload)).hexdigest() != fingerprint
