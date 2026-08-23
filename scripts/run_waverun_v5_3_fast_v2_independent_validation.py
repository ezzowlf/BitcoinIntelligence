"""Fail-closed independent-validation gate for the frozen V5.3 Fast V2 hypothesis."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HYPOTHESIS_SHA256 = "49bc145432b187f66c1c1d577dc8fad5b39c93f786e8bb286b20b17e2c6c5dea"
BASE_DEFINITION_SHA256 = (
    "cbeb17ec5e2bc819fc54e01da0ed8a70bc319cb248d4aa6b225147b56a946f60"
)
DISCOVERY_END = date(2026, 7, 31)
RESERVED_HOLDOUT = {date(2026, 8, 16), date(2026, 8, 17)}
MINIMUM_SIGNALS = 100
VETO_THRESHOLD = 0.1502250887673838

OUT = ROOT / "data/reports/waverun_v5_3_fast_v2_independent_validation"
JSON_PATH = OUT / "independent_validation.json"
REPORT_PATH = ROOT / "WAVERUN_V5_3_FAST_V2_INDEPENDENT_VALIDATION.md"


def derived_dates() -> list[date]:
    dates = []
    for path in (ROOT / "runtime/waverun_data/derived").rglob("*.parquet"):
        try:
            dates.append(date.fromisoformat(path.stem))
        except ValueError:
            continue
    return sorted(set(dates))


def validate_inventory(dates: list[date]) -> dict[str, Any]:
    discovery_dates = [day for day in dates if day <= DISCOVERY_END]
    reserved_present = sorted(day for day in dates if day in RESERVED_HOLDOUT)
    independent_dates = sorted(
        day for day in dates if day > DISCOVERY_END and day not in RESERVED_HOLDOUT
    )
    return {
        "all_derived_dates": len(dates),
        "first_derived_date": None if not dates else dates[0].isoformat(),
        "last_derived_date": None if not dates else dates[-1].isoformat(),
        "discovery_input_dates": len(discovery_dates),
        "independent_dates": [day.isoformat() for day in independent_dates],
        "independent_day_count": len(independent_dates),
        "reserved_holdout_present_but_unopened": [
            day.isoformat() for day in reserved_present
        ],
        "reserved_holdout_accessed": False,
    }


def build_result(inventory: dict[str, Any]) -> dict[str, Any]:
    enough_data = inventory["independent_day_count"] > 0
    if enough_data:
        raise RuntimeError(
            "Independent derived dates now exist; implement path evaluation before reporting a result"
        )
    unavailable = {
        "n": 0,
        "rate": None,
        "status": "NOT_ESTIMABLE_NO_INDEPENDENT_DATA",
    }
    return {
        "attempt_status": "INSUFFICIENT_DATA",
        "reason": (
            "No derived period after the 2026-07-31 discovery cutoff is available, "
            "and the protocol forbids opening the reserved 2026-08-16/17 holdout."
        ),
        "hypothesis": {
            "sha256": HYPOTHESIS_SHA256,
            "base_definition_sha256": BASE_DEFINITION_SHA256,
            "direction": "SHORT",
            "veto": {
                "feature": "spot_pressure_10s",
                "operator": "<=",
                "threshold": VETO_THRESHOLD,
            },
            "booster": None,
            "primary_outcome": "SHORT MFE >= $100 within 300 seconds",
        },
        "inventory": inventory,
        "minimum_sample_requirement": MINIMUM_SIGNALS,
        "total_v2_signals": 0,
        "signals_per_day": None,
        "targets_300s": {
            str(target): dict(unavailable)
            for target in (25, 50, 75, 100, 150, 200, 300, 500)
        },
        "comparable_short_base_rate": dict(unavailable),
        "absolute_lift_percentage_points": None,
        "relative_lift_times": None,
        "mae_before_100": {key: None for key in ("p50", "p75", "p90", "max")},
        "time_to_first_positive_s": {key: None for key in ("p50", "p75", "p90")},
        "time_to_100_s": {key: None for key in ("p50", "p75", "p90")},
        "path_classes": {
            "IMMEDIATE_CONTINUATION": None,
            "PULLBACK_THEN_CONTINUATION": None,
            "WRONG_DIRECTION": None,
        },
        "veto_audit": {
            "blocked_signals": None,
            "blocked_would_have_failed": None,
            "blocked_would_have_won": None,
        },
        "discovery_rate": 29 / 42,
        "oos_rate": None,
        "oos_base_rate": None,
        "oos_lift": None,
        "wilson_95_ci": None,
        "gates": {
            "three_signals_per_day": "NOT_EVALUABLE_INSUFFICIENT_DATA",
            "at_least_65pct_oos": "NOT_EVALUABLE_INSUFFICIENT_DATA",
            "at_least_70pct_oos": "NOT_EVALUABLE_INSUFFICIENT_DATA",
        },
        "veto_replicated": "INSUFFICIENT",
        "v5_3_fast_v2": "INSUFFICIENT",
        "next_stage": (
            "Acquire and derive a genuinely post-2026-07-31 period without changing "
            "the hypothesis; accumulate at least 100 independent V2 signals before judgment."
        ),
        "oos_verified": False,
        "holdout": "CLOSED",
        "execution": "DISABLED",
    }


def render_report(result: dict[str, Any]) -> str:
    inventory = result["inventory"]
    return "\n".join(
        [
            "# WAVERUN V5.3 FAST V2 INDEPENDENT VALIDATION",
            "",
            "## Result",
            "",
            "**INSUFFICIENT_DATA — no independent validation population is currently available.**",
            "",
            f"- Hypothesis SHA-256: `{HYPOTHESIS_SHA256}`",
            f"- Base definition SHA-256: `{BASE_DEFINITION_SHA256}`",
            f"- Frozen veto: `spot_pressure_10s <= {VETO_THRESHOLD:.17g}`",
            "- Booster: `NONE`",
            "- Primary outcome: SHORT MFE >= $100 within 300 seconds",
            "",
            "## Independent-data gate",
            "",
            f"- Existing derived dates: **{inventory['all_derived_dates']}**",
            f"- Existing range: **{inventory['first_derived_date']} through {inventory['last_derived_date']}**",
            f"- Dates available after the discovery cutoff: **{inventory['independent_day_count']}**",
            "- Reserved 2026-08-16/17 holdout accessed: **NO**",
            f"- Protocol minimum: **{MINIMUM_SIGNALS} independent candidates**",
            "",
            "All existing derived days through 2026-07-31 were searchable inputs to the discovery process that produced the 47 candidates and the veto. Reusing them would be in-sample, not independent validation.",
            "",
            "## Required metrics",
            "",
            "- TOTAL V2 SIGNALS: **0 independent observations available**",
            "- SIGNALS/DAY: **NOT ESTIMABLE**",
            "- $25/$50/$75/$100/$150/$200/$300/$500 within 300s: **NOT ESTIMABLE**",
            "- COMPARABLE SHORT BASE RATE: **NOT ESTIMABLE**",
            "- ABSOLUTE / RELATIVE LIFT: **NOT ESTIMABLE**",
            "- MAE BEFORE $100: **NOT ESTIMABLE**",
            "- TIME TO FIRST POSITIVE / $100: **NOT ESTIMABLE**",
            "- PATH CLASSES: **NOT ESTIMABLE**",
            "- VETO BLOCK AUDIT: **NOT ESTIMABLE**",
            "- WILSON 95% CI: **NOT ESTIMABLE**",
            "",
            "## Decision",
            "",
            "- DISCOVERY RATE: **29/42 = 69.05%**",
            "- OOS RATE: **NOT ESTIMABLE**",
            "- 3 SIGNALS/DAY: **NOT EVALUABLE / INSUFFICIENT**",
            "- >=65% OOS: **NOT EVALUABLE / INSUFFICIENT**",
            "- >=70% OOS: **NOT EVALUABLE / INSUFFICIENT**",
            "- VETO REPLICATED: **INSUFFICIENT**",
            "- V5.3 FAST V2: **INSUFFICIENT**",
            "",
            "Next action: derive a genuinely post-2026-07-31, non-holdout period under the unchanged pipeline and accumulate at least 100 independent V2 signals. Do not modify the veto after seeing future results.",
            "",
            "HOLDOUT: CLOSED",
            "EXECUTION: DISABLED",
            "",
        ]
    )


def main() -> None:
    result = build_result(validate_inventory(derived_dates()))
    OUT.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_bytes((json.dumps(result, indent=2) + "\n").encode("utf-8"))
    REPORT_PATH.write_bytes(render_report(result).encode("utf-8"))


if __name__ == "__main__":
    main()
