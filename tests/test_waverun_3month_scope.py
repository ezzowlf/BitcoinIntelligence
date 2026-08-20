import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_waverun_3month_deep_research.py"
SPEC = importlib.util.spec_from_file_location("waverun_q1_research", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
research = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(research)


def test_three_month_scope_and_case_days_are_not_model_proof():
    assert research.START == date(2025, 1, 1)
    assert research.END == date(2025, 3, 31)
    for split in research.SPLITS:
        assert not research.CASE_DAYS.intersection(research.split_days(split))


def test_final_holdout_is_outside_q1_research_scope():
    assert all(day.year == 2025 for day in research.days(research.START, research.END))
    assert research.ASSUMED_COST_BP > 0


def test_split_projection_has_unique_columns():
    features = ["hour_utc", "weekday", "flow_pressure"]
    labels = [
        item
        for horizon in research.HORIZONS
        for item in (f"future_return_{horizon}s", f"direction_{horizon}s", f"move_{horizon}s")
    ]
    context = ["timestamp", "regime", "origin", "month", "hour_utc", "weekday", "case_anchor_day"]
    columns = list(dict.fromkeys([*context, *features, *labels]))
    assert len(columns) == len(set(columns))


def test_independent_entries_enforce_horizon_cooldown():
    predictions = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(
                ["2025-03-16T00:00:00Z", "2025-03-16T00:00:05Z", "2025-03-16T00:03:00Z"]
            ),
            "confidence": [0.9, 0.95, 0.8],
        }
    )
    selected = research.independent_entries(predictions, threshold=0.75, horizon=180)
    assert selected.timestamp.tolist() == [predictions.timestamp.iloc[0], predictions.timestamp.iloc[2]]
