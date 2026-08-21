from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
V1_PATH = ROOT / "scripts" / "run_waverun_v1_blind_validation.py"
SPEC = importlib.util.spec_from_file_location("v1", V1_PATH)
assert SPEC is not None and SPEC.loader is not None
v1 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v1)

from bitcoin_cycle_analyzer.short_term.research_protocol import assert_days_allowed
from bitcoin_cycle_analyzer.short_term.waverun_v4 import (
    ADVERSE_USD,
    HORIZONS_SECONDS,
    MAGNITUDES_USD,
    source_health,
    v4_gate,
)

OUTPUT = ROOT / "data" / "reports" / "waverun_v4"
CREATED_AT = "2026-08-21T00:00:00+00:00"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def crossing(path: np.ndarray, level: float) -> int | None:
    hits = np.flatnonzero(path >= level)
    return None if not len(hits) else int(hits[0] * 5)


def count_moves(frame: pd.DataFrame) -> dict[int, int]:
    prices = frame.mid.to_numpy(float)
    times = pd.DatetimeIndex(frame.timestamp)
    window = 120
    position = 0
    counts = {target: 0 for target in MAGNITUDES_USD}
    while position < len(frame) - window:
        if times[position].date() != times[position + window].date():
            position += 1
            continue
        path = prices[position : position + window + 1]
        up = crossing(path - path[0], 100)
        down = crossing(path[0] - path, 100)
        available = [
            (time, direction)
            for time, direction in ((up, 1), (down, -1))
            if time is not None
        ]
        if not available:
            position += 1
            continue
        _, direction = min(available)
        maximum = float((direction * (path - path[0])).max())
        for target in MAGNITUDES_USD:
            counts[target] += maximum >= target
        position += window
    return counts


def load_periods() -> dict[str, pd.DataFrame]:
    periods = {}
    for name, bounds in v1.q1.SPLITS.items():
        days = [day for day in v1.q1.days(*bounds) if day not in v1.q1.CASE_DAYS]
        periods[f"Q1_{name.upper()}"] = pd.concat(
            [
                pd.read_parquet(v1.q1.derived_path(day), columns=["timestamp", "mid"])
                for day in days
            ],
            ignore_index=True,
        )
    for name, bounds in v1.PERIODS.items():
        periods[name] = pd.concat(
            [
                pd.read_parquet(v1.blind_path(day), columns=["timestamp", "mid"])
                for day in v1.q1.days(*bounds)
            ],
            ignore_index=True,
        )
    return periods


def reports(result: dict) -> None:
    provider = """# WAVERUN V4 Data Provider Evaluation

| Provider/source | L2 | Liquidations/OI/Funding | Multi-venue | Access decision |
|---|---|---|---|---|
| Existing local Binance archives | No historical L2 | AggTrades only | Binance Spot/Futures | USE FREE FIRST |
| Tardis.dev | Tick L2, snapshots, replay | Yes | 50+ exchanges | BUY PILOT AFTER FREE SAMPLE |
| Amberdata | Events/snapshots | Yes | Broad CEX | LATER / quote comparison |
| Kaiko | Tick/aggregated L2 | Derivatives/OI/liquidations | Broad CEX | LATER / institutional alternative |
| Official exchange APIs/archives | Mostly current snapshots; limited historical L2 | Venue-specific | Manual integration | USE FREE FIRST |

Tardis is the highest-value pilot because one normalized clocked dataset can cover L2, liquidations, derivative tickers and cross-exchange replay. No purchase was made. Official documentation: https://docs.tardis.dev/downloadable-csv-files, https://docs.amberdata.io/data-dictionary/coverage/exchange-coverage, https://docs.kaiko.com/explore-our-data/data-dictionary.
"""
    info = f"""# WAVERUN V4 Information Expansion Report

Final classification: **{result["final_decision"]}**

Locally activated new predictive sources: **none**. Existing data contains Binance Spot/Futures trades and prices, but no historical L2, liquidations, OI, funding, basis, options or causally reconstructable multi-exchange book state over the 209-day research universe.

The $100/$150 opportunity ladder was activated from existing prices, but this expands labels, not information. No new model was trained because no new information family overlaps the chronological research periods.

Execution `DISABLED`; holdout closed; V1/V2/V3 unchanged.
"""
    l2 = "# WAVERUN V4 L2 Research Report\n\nStatus: `BLOCKED_NO_HISTORICAL_L2_ACTIVATED`. Book snapshot, sequence, microprice, imbalance, pulling and stacking contracts are implemented and tested, but no OOS usefulness is claimed.\n"
    derivatives = "# WAVERUN V4 Derivatives Intelligence Report\n\nLiquidations, OI, funding, basis and options: `NOT LOCALLY AVAILABLE` for overlapping research. No causal or OOS conclusion.\n"
    cross = "# WAVERUN V4 Cross-Exchange Report\n\nOnly Binance Spot/Futures overlap exists. Coinbase/Bybit/OKX confirmation and venue leadership remain `UNAVAILABLE`; no divergence blocker was promoted.\n"
    rows = [
        "# WAVERUN V4 Move Frontier",
        "",
        "Definition: `$100`-anchored, non-overlapping 600-second windows. These are raw market opportunities, not predictable signals. Counts are not directly comparable to earlier `$200`-anchored opportunity counts.",
        "",
        "| Magnitude | Raw opportunities/day | Predictable/day | Best adverse | Best horizon | Best OOS precision | CI | Net EV | Lead | Remaining |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for target in MAGNITUDES_USD:
        rows.append(
            f"| ${target} | {result['move_frontier'][str(target)]['raw_per_day']:.2f} | 0 | n/a | n/a | Not established | n/a | n/a | n/a | n/a |"
        )
    frontier = "# WAVERUN V4 Product Frontier\n\n| Signals/day | Best defensible precision |\n|---:|---:|\n| 3 | Not supported |\n| 5 | Not supported |\n| 7 | Not supported |\n| 10 | Not supported |\n\n| Required precision | Max defensible signals/day |\n|---:|---:|\n| 70% | 0 |\n| 75% | 0 |\n| 80% | 0 |\n| 85% | 0 |\n| 90% | 0 |\n"
    truefalse = "# WAVERUN V4 True False Precursor Report\n\nNo NEW information source was activated, so no new true/false separation can be measured. Existing AggTrade-only ceiling remains unchanged.\n"
    failure = "# WAVERUN V4 Failure Knowledge\n\n- Expanding targets to $100/$150 increases opportunities but not proven predictability.\n- L2/OI/liquidation/cross-exchange hypotheses remain UNTESTED, not failed.\n- Another AggTrade-only model would repeat a rejected search.\n"
    findings = "# WAVERUN V4 Master Findings\n\n1. $100/$150 labels materially increase raw market opportunity.\n2. Raw opportunity is not predictive frequency.\n3. No new causal information overlaps the research periods locally.\n4. Historical L2 is the highest-value missing source.\n5. Liquidations/OI are next priority.\n6. Cross-exchange confirmation cannot be tested from Binance-only data.\n7. Vantage Bid/Ask remains execution-critical, not a substitute for predictive microstructure.\n8. Current bottleneck is DATA, followed by execution truth and concept drift.\n9. No V4 challenger is eligible.\n10. A bounded Tardis free-sample pilot should precede purchase.\n"
    for name, text in {
        "WAVERUN_V4_DATA_PROVIDER_EVALUATION.md": provider,
        "WAVERUN_V4_INFORMATION_EXPANSION_REPORT.md": info,
        "WAVERUN_V4_L2_RESEARCH_REPORT.md": l2,
        "WAVERUN_V4_DERIVATIVES_INTELLIGENCE_REPORT.md": derivatives,
        "WAVERUN_V4_CROSS_EXCHANGE_REPORT.md": cross,
        "WAVERUN_V4_MOVE_FRONTIER.md": "\n".join(rows) + "\n",
        "WAVERUN_V4_PRODUCT_FRONTIER.md": frontier,
        "WAVERUN_V4_TRUE_FALSE_PRECURSOR_REPORT.md": truefalse,
        "WAVERUN_V4_FAILURE_KNOWLEDGE.md": failure,
        "WAVERUN_V4_MASTER_FINDINGS.md": findings,
    }.items():
        write_text(ROOT / name, text)


def main() -> None:
    assert_days_allowed([])
    frozen = v1.verify_freeze()
    periods = load_periods()
    counts = {target: 0 for target in MAGNITUDES_USD}
    for frame in periods.values():
        for target, value in count_moves(frame).items():
            counts[target] += value
    days = sum(frame.timestamp.dt.date.nunique() for frame in periods.values())
    sources = {
        name: source_health(0, 0, 0, 0, 0)
        for name in (
            "historical_l2",
            "liquidations",
            "open_interest",
            "cross_exchange",
            "funding",
            "basis",
            "options",
            "point_in_time_events",
            "vantage_bid_ask",
        )
    }
    result = {
        "research_id": "WAVERUN_V4_INFORMATION_EXPANSION",
        "execution": "DISABLED",
        "holdout_opened": False,
        "v1_fingerprint": frozen["fingerprint_sha256"],
        "v2_unchanged": True,
        "v3_unchanged": True,
        "magnitudes_usd": MAGNITUDES_USD,
        "adverse_usd": ADVERSE_USD,
        "horizons_seconds": HORIZONS_SECONDS,
        "research_days": days,
        "opportunity_definition": "$100-anchored, non-overlapping 600-second windows; raw market opportunities only",
        "comparison_warning": "Counts are not directly comparable to earlier $200-anchored opportunity counts.",
        "move_frontier": {
            str(target): {
                "raw_opportunities": counts[target],
                "raw_per_day": counts[target] / days,
                "predictable_per_day": 0,
                "oos_precision": None,
            }
            for target in MAGNITUDES_USD
        },
        "new_source_health": sources,
        "new_information_activated": False,
        "information_gain_status": "UNMEASURABLE_NO_NEW_OVERLAP",
        "v4_gate": v4_gate({}),
        "candidate_frozen": False,
        "final_decision": "V4 BLOCKED BY DATA AVAILABILITY",
        "product_status": {
            "3/day_70": "FAIL",
            "5/day_75": "FAIL",
            "3/day_80": "FAIL",
            "90_elite": "NOT_FOUND",
        },
        "provider_decision": {
            "BUY_NOW": [],
            "USE_FREE_FIRST": [
                "official exchange archives/APIs",
                "Tardis first-day-of-month samples",
            ],
            "LATER": ["Tardis paid pilot", "Amberdata", "Kaiko"],
            "NOT_WORTH_IT": ["unverified datasets without event/receive timestamps"],
        },
        "created_at": CREATED_AT,
    }
    write_json(OUTPUT / "information_expansion_result.json", result)
    write_json(OUTPUT / "source_inventory.json", sources)
    reports(result)
    print(
        json.dumps(
            {
                "decision": result["final_decision"],
                "days": days,
                "frontier": result["move_frontier"],
                "new_information": False,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
