from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "run_waverun_v5_3_fast_v2_independent_validation.py"
)
SPEC = importlib.util.spec_from_file_location("v53_fast_v2_validation", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_inventory_excludes_discovery_and_reserved_holdout() -> None:
    inventory = MODULE.validate_inventory(
        [date(2026, 7, 31), date(2026, 8, 1), date(2026, 8, 16)]
    )
    assert inventory["independent_dates"] == ["2026-08-01"]
    assert inventory["reserved_holdout_present_but_unopened"] == ["2026-08-16"]
    assert inventory["reserved_holdout_accessed"] is False


def test_no_independent_data_is_insufficient_not_failure() -> None:
    inventory = MODULE.validate_inventory([date(2026, 7, 31)])
    result = MODULE.build_result(inventory)
    assert result["v5_3_fast_v2"] == "INSUFFICIENT"
    assert result["oos_rate"] is None
    assert result["holdout"] == "CLOSED"
    assert result["execution"] == "DISABLED"
