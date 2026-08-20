from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.research_protocol import (
    FINAL_HOLDOUT,
    assert_days_allowed,
)
from bitcoin_cycle_analyzer.short_term.waverun_v2 import (
    FindingsStore,
    OpportunityRecord,
    as_record,
    opportunity_id,
    pareto_frontier,
    prefreeze_gate,
)

HARD = ROOT / "data" / "reports" / "waverun_v2_hard_moves"
OUTPUT = ROOT / "data" / "reports" / "waverun_v2_strategy"
REPORT = ROOT / "WAVERUN_V2_STRATEGY_MASTER_REPORT.md"
MEMORY = ROOT / "runtime" / "waverun_v2_findings.sqlite"
V1_FINGERPRINT = "a61a4229635da3e3869b08371e3d7dd38290091951b4488a2bda7df13c2a0f60"
SYNTHESIS_CREATED_AT = "2026-08-21T00:00:00+00:00"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_gzip(path: Path) -> list[dict]:
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def flatten_cells(hard: dict) -> list[dict]:
    rows = []
    for adverse, targets in hard["full_barrier_grid"].items():
        for target, horizons in targets.items():
            for horizon, cell in horizons.items():
                rows.append({
                    "target": int(target), "adverse": int(adverse), "horizon": int(horizon),
                    "precision": cell["precision"], "signals": cell["evaluated_signals"],
                    "signals_per_day": cell["evaluated_signals"] / hard["days"],
                    "successful_per_day": cell["successful_opportunities_per_day"],
                    "net_ev": cell["proxy_net_ev_usd"], "wilson_ci95": cell["wilson_ci95"],
                    "lead_time": cell["median_lead_time_seconds"],
                })
    return rows


def build_opportunities(precursors: list[dict]) -> list[dict]:
    output = []
    for record in precursors:
        outcome = record["paths"]["600"]["200"]["100"]
        contradictions = []
        t0 = record["history"]["T0"]
        if t0["origin"] == "DIVERGENT":
            contradictions.append("SPOT_FUTURES_DIVERGENCE")
        if (t0["expansion_score"] or 0) > 70:
            contradictions.append("POSSIBLY_LATE_EXPANSION")
        output.append(as_record(OpportunityRecord(
            opportunity_id=opportunity_id(record["timestamp"], record["direction"], 200, 600),
            timestamp=record["timestamp"], direction=record["direction"],
            setup_family=record["mechanism_hypothesis"], primary_horizon=600,
            primary_target=200, adverse_barrier=100, calibrated_probability=None,
            expected_remaining_move=record["remaining_move_usd"],
            evidence={"source": "FROZEN_V1_BASELINE", "v1_confidence_not_barrier_calibrated": record["confidence"]},
            contradictions=contradictions, state="ABSTAIN",
            outcome="TRUE_POSITIVE" if outcome["success"] else "FALSE_POSITIVE",
        )))
    return output


def finding(category: str, statement: str, evidence: dict, period: str, n: int, status: str, supports: str = "", contradicts: str = "") -> dict:
    return {
        "category": category, "statement": statement, "evidence": evidence, "period": period,
        "sample_size": n, "confidence": "HIGH" if status in {"REPLICATED", "REFUTED"} else "MEDIUM",
        "supports": supports, "contradicts": contradicts, "status": status,
        "created_at": SYNTHESIS_CREATED_AT,
    }


def write_report(result: dict) -> None:
    best = result["best_current_configuration"]
    availability = result["move_availability"]
    lines = [
        "# WAVERUN V2 Strategy Master Report", "",
        f"Final decision: **{result['final_decision']}**", "",
        "Product target `>=3/day & >=70%`: **FAIL**. No V2 candidate was frozen and the final August holdout remains closed.", "",
        "## Data used", "",
        "Q1 2025 discovery/train/validation/walk-forward excluding the three screenshot case days; blind April–June 2025; later OOS July 2026. In total: 209 research days, 14,616 non-overlapping hard-move windows, and 159 frozen-V1 baseline signals. Binance is a research proxy; Vantage Bid/Ask history and historical L2 remain unavailable.", "",
        "## What WAVERUN learned", "",
        "V1 did not generalize. Meaningful hard moves are common enough in the market, but the existing causal detector cannot isolate them with production precision. Broad MACD did not improve prior OOS work; expansion and Spot/Futures confirmation remain useful hypotheses, not stable rules. DOWN was somewhat easier than UP in the $200/600s/$100 baseline, but neither passed.", "",
        "## True versus false precursors", "",
        "At $200 before $100 within 600s, 66 of 159 V1 opportunities succeeded and 93 failed. Spot/Futures confirmation, expansion and extreme MACD all remained below 50% in this baseline. The false library points to divergence, late expansion, absorption/weak price response and pressure decay as blockers requiring unbiased OOS tests.", "",
        "## Move size", "",
        "| Target | Historical opportunities/day | Best current OOS precision | Predictive signals/day | Status |",
        "|---:|---:|---:|---:|---|",
    ]
    for target in (200, 300, 400, 500, 600, 800):
        lines.append(f"| ${target} | {availability[str(target)]['moves_per_day']:.2f} | Not established | 0 | No V2 OOS model |")
    lines += [
        "", "## Unified strategy architecture", "",
        "One system is retained: causal market state → continuation/reversion router → direction → monotone magnitude probabilities → target-before-adverse probability → remaining-move/readiness gate → `ACTIVITY_BUILDING / WATCH / ARMED / SIGNAL / ABSTAIN`. Setup families are explanations inside the router, never separately optimized trading systems.", "",
        "Current defensible behavior is `ABSTAIN`: there is no calibrated V2 barrier model. A future signal requires aligned Spot/Futures evidence, efficient price response, early rather than mature expansion, sufficient remaining move, no absorption/divergence blocker, positive realistic-cost EV and a chronologically validated calibrated probability.", "",
        "## When WAVERUN should not signal", "",
        "Spot/Futures divergence; strong flow without price response; mature/exhausting expansion; pressure decay; adverse excursion already too large; less than $200 estimated remaining opportunity; event evidence without point-in-time timestamps; missing Vantage execution metadata; or any probability not calibrated on later unseen data.", "",
        "## Current model evidence", "",
        "Prior bounded comparisons covered Logistic, GradientBoosting and RandomForest in the seconds-research pipeline. Logistic was provisionally strongest, but walk-forward stability failed. HistGradientBoosting and ExtraTrees are queued for the unbiased barrier dataset; they were not fit to the positive-only move library plus V1-selected negatives because that would create selection bias.", "",
        "## Feature evidence", "",
        "- Flow and pressure: economically plausible, but absolute/extreme pressure alone creates many false positives.",
        "- Spot/Futures confirmation: useful interaction hypothesis; not independently >=70% OOS.",
        "- Expansion: strongest prior diagnostic subgroup, but time stability was not proven.",
        "- MACD: broad use hurt prior OOS; anomaly/acceleration interactions remain bounded research hypotheses.",
        "- Mean reversion: displacement alone is rejected; only exhaustion + absorption + structure change merits further testing.", "",
        "## Precision-frequency goal", "",
        "| Target frequency | Best validated precision | N | Net EV | Target magnitude |",
        "|---:|---:|---:|---:|---:|",
        "| 3/day | Not supported | 0 | n/a | n/a |", "| 5/day | Not supported | 0 | n/a | n/a |",
        "| 7/day | Not supported | 0 | n/a | n/a |", "| 10/day | Not supported | 0 | n/a | n/a |", "",
        "## Precision ladder", "",
        "| Precision | Maximum stable signals/day | Status |", "|---:|---:|---|",
        "| 70% | 0 | Not found |", "| 75% | 0 | Not found |", "| 80% | 0 | Not found |",
        "| 85% | 0 | Not found |", "| 90% | 0 | Not found |", "",
        "## Best current configuration", "",
        f"Best diagnostic baseline only: target ${best['target']}, adverse ${best['adverse']}, horizon {best['horizon']}s, frozen V1 source, precision {best['precision']:.2%}, {best['signals_per_day']:.2f} evaluated signals/day, proxy EV ${best['net_ev']:+.2f}. This is not a V2 strategy and is not eligible for freeze.", "",
        "## Calibration and magnitude consistency", "",
        "No 70/80/90 probability is displayed. Future P(>=200...>=800) outputs must be calibrated with Brier, Log Loss, ECE and reliability curves, then projected to non-increasing magnitude probabilities when necessary.", "",
        "## Limitations", "",
        "No historical L2; no real Vantage Bid/Ask cost validation; Binance proxy execution; selected-negative bias in existing false precursors; concept drift between 2025 and July 2026; limited point-in-time event history; no unbiased V2 base-state dataset yet.", "",
        "## Next research queue", "",
        "1. Build unbiased causal base-state samples at fixed intervals with embargoed target paths.",
        "2. Freeze fresh discovery/train/validation/walk-forward boundaries before model fitting.",
        "3. Compare Logistic, HistGradientBoosting, GradientBoosting, RandomForest and ExtraTrees on identical barrier labels.",
        "4. Test confirmation/absorption, early expansion, pressure acceleration, failed pullback and MACD interactions as bounded ablations.",
        "5. Calibrate the winning architecture and evaluate monthly/fold stability; only then consider a V2 freeze.", "",
        "## Final gates", "",
        "- `>=3/day & >=70%`: FAIL", "- `>=5/day & >=75%`: FAIL", "- `>=3/day & >=80%`: FAIL",
        "- `90% ELITE`: NOT FOUND", "- V2 freeze: NOT PERMITTED", "- Execution: `DISABLED`", "- Final holdout: `CLOSED / UNTOUCHED`",
    ]
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    assert_days_allowed([])
    hard = load_json(HARD / "hard_move_result.json")
    if hard["v1_fingerprint"] != V1_FINGERPRINT or hard["holdout"] != "CLOSED_UNTOUCHED":
        raise RuntimeError("V1/holdout integrity failure")
    precursors = load_gzip(HARD / "precursor_library.json.gz")
    cells = flatten_cells(hard)
    frontier = pareto_frontier(cells)
    best = max(cells, key=lambda row: (row["precision"], row["net_ev"]))
    gate = prefreeze_gate({
        "precision": best["precision"], "net_ev": best["net_ev"], "signals_per_day": best["signals_per_day"],
        "signals": best["signals"], "positive_folds": 0, "folds": 1, "parameter_cliff": True,
    })
    opportunities = build_opportunities(precursors)
    findings = [
        finding("V1", "Frozen V1 failed to generalize on later blind data.", {"new_oos_precision": 0.6042}, "2025-04-01..2026-07-31", 144, "REFUTED", contradicts="V1 high-precision hypothesis"),
        finding("HARD_MOVE", "Existing V1 barrier baseline peaks below the product precision gate.", {"best": best}, "2025-03-16..2026-07-31", 159, "REPLICATED", contradicts="V2 pre-freeze gate"),
        finding("MACD", "Broad MACD did not add stable OOS value; anomaly interactions remain unproven.", {"hard_baseline_extreme_precision": 0.4052}, "Q1 2025..Jul 2026", 153, "OBSERVED"),
        finding("EXPANSION", "Expansion is diagnostic but not chronologically stable enough for promotion.", {"hard_baseline_early_expansion_precision": 0.425}, "Q1 2025..Jul 2026", 120, "INCONCLUSIVE"),
        finding("FLOW", "Spot/Futures confirmation alone remains below the barrier precision gate.", {"precision": 0.4659}, "Q1 2025..Jul 2026", 88, "INCONCLUSIVE"),
    ]
    store = FindingsStore(MEMORY)
    finding_ids = [store.append(row) for row in findings]
    result = {
        "research_id": "WAVERUN_V2_STRATEGY_SYNTHESIS", "execution": "DISABLED",
        "final_holdout_requested": False, "final_holdout_dates": sorted(day.isoformat() for day in FINAL_HOLDOUT),
        "v1_fingerprint": V1_FINGERPRINT, "development_splits": {
            "DISCOVERY": "2025-01-01..2025-02-09", "TRAIN": "2025-02-10..2025-03-15",
            "VALIDATION": "2025-03-16..2025-06-30", "WALK_FORWARD": "2026-07-01..2026-07-31",
            "FINAL_HOLDOUT": "2026-08-16..2026-08-17 CLOSED",
        },
        "final_decision": "NO ROBUST V2 STRATEGY FOUND", "candidate_frozen": False,
        "prefreeze_gate": gate, "best_current_configuration": best,
        "pareto_frontier": frontier, "move_availability": hard["move_library_summary"],
        "opportunity_records": len(opportunities), "findings": findings, "finding_ids": finding_ids,
        "model_comparison_status": {
            "Logistic": "PRIOR_PROVISIONAL_NOT_STABLE", "GradientBoosting": "PRIOR_SCREENED_NOT_SELECTED",
            "RandomForest": "PRIOR_SCREENED_NOT_SELECTED", "HistGradientBoosting": "QUEUED_UNBIASED_DATASET_REQUIRED",
            "ExtraTrees": "QUEUED_UNBIASED_DATASET_REQUIRED",
        },
        "product_status": {">=3/day_>=70%": "FAIL", ">=5/day_>=75%": "FAIL", ">=3/day_>=80%": "FAIL", "90%_elite": "NOT_FOUND"},
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_json(OUTPUT / "strategy_result.json", result)
    write_json(OUTPUT / "opportunity_records.json", opportunities)
    write_json(OUTPUT / "findings.json", findings)
    write_report(result)
    print(json.dumps({"decision": result["final_decision"], "prefreeze": gate, "opportunities": len(opportunities), "holdout_opened": False}, indent=2))


if __name__ == "__main__":
    main()
