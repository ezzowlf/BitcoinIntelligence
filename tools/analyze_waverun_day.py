from __future__ import annotations

import argparse
import bisect
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path


def stamp(value: str) -> float:
    return datetime.fromisoformat(value.replace(" ", "T")).timestamp()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("runtime", type=Path)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--engine-source", type=Path)
    parser.add_argument("--summary-only", action="store_true")
    args = parser.parse_args()
    start, end = stamp(args.start), stamp(args.end)

    ticks: list[tuple[float, float, float]] = []
    with (args.runtime / "vantage_ticks.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            ts = stamp(row["timestamp"])
            if start <= ts < end:
                ticks.append((ts, float(row["bid"]), float(row["ask"])))
    tick_times = [row[0] for row in ticks]

    evaluations = 0
    raw_counts: Counter[str] = Counter()
    directions: Counter[str] = Counter()
    missing_counts: Counter[int] = Counter()
    only_missing: Counter[str] = Counter()
    episodes: list[dict] = []
    current: dict | None = None
    confirmed_episodes: list[dict] = []
    confirmed_current: dict | None = None
    clock_value = [start]
    machine = None
    Evidence = None
    if args.engine_source:
        sys.path.insert(0, str(args.engine_source))
        from bitcoin_cycle_analyzer.short_term.presignal_state import (
            Evidence as EvidenceType,
        )
        from bitcoin_cycle_analyzer.short_term.presignal_state import (
            PreSignalStateMachine,
        )
        Evidence = EvidenceType
        machine = PreSignalStateMachine(clock=lambda: clock_value[0])

    with (args.runtime / "pre_gate_candidates.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            ts = stamp(row["timestamp"])
            if not start <= ts < end:
                continue
            evaluations += 1
            direction = row.get("direction_bias") or "NEUTRAL"
            directions[direction] += 1
            pressure = float(row.get("long_pressure_score" if direction == "LONG" else "short_pressure_score", 0) or 0)
            momentum = row.get("momentum_pressure_state") or {}
            returns = momentum.get("returns") or {}
            ret60 = returns.get("60", returns.get(60))
            range_expansion = momentum.get("range_expansion")
            signals = {item.get("name"): item for item in row.get("signals", [])}
            spot = (signals.get("spot_flow_10s") or {}).get("direction")
            futures = (signals.get("futures_flow_10s") or {}).get("direction")
            flow = spot in {"BULLISH", "BEARISH"} and spot == futures
            imbalance = momentum.get("l2_imbalance")
            l2 = isinstance(imbalance, (int, float)) and ((direction == "LONG" and imbalance > 0) or (direction == "SHORT" and imbalance < 0))
            signed60 = ret60 if direction == "LONG" else -ret60 if isinstance(ret60, (int, float)) else None
            move = (isinstance(signed60, (int, float)) and signed60 >= 0.0003) or (isinstance(range_expansion, (int, float)) and range_expansion >= 1.3 and direction in {"LONG", "SHORT"})
            conditions = {
                "richtung": direction in {"LONG", "SHORT"} and pressure >= 35,
                "momentum": move,
                "futures": flow,
                "orderbuch": l2,
                # These are false in the shipped UI because latest.json.state is NEUTRAL.
                "zustand": False,
                "scharf": False,
                "datenqualitaet": row.get("availability", {}).get("mt5") == "AVAILABLE",
            }
            missing = [key for key, value in conditions.items() if not value]
            build = sum(conditions[key] for key in ("richtung", "momentum", "futures", "orderbuch", "zustand"))
            raw = "SIGNAL_NAHE" if len(missing) <= 1 else "SETUP_ENTSTEHT" if build >= 3 else "BEOBACHTEN" if build else "RUHIG"
            raw_counts[raw] += 1

            if machine is not None and Evidence is not None:
                previous = machine.state
                clock_value[0] = ts
                snapshot = machine.update(Evidence(
                    setup_state="NEUTRAL",
                    direction=direction,
                    pressure=pressure,
                    flow_agreement="CONFIRMED" if flow else "DIVERGENT",
                    l2_aligned=l2,
                    return_60s=ret60,
                    range_expansion=range_expansion,
                    sources_online=row.get("availability", {}).get("mt5") == "AVAILABLE",
                    price_live=row.get("availability", {}).get("mt5") == "AVAILABLE",
                    contradictions=tuple(row.get("contradictions") or ()),
                ))
                state = snapshot["state"]
                if state == "SETUP_ENTSTEHT":
                    if confirmed_current is None:
                        confirmed_current = {"start": ts, "last": ts, "direction": direction, "rows": 1, "best_missing": list(snapshot["missing"])}
                    else:
                        confirmed_current["last"] = ts
                        confirmed_current["rows"] += 1
                        if len(snapshot["missing"]) < len(confirmed_current["best_missing"]):
                            confirmed_current["best_missing"] = list(snapshot["missing"])
                elif confirmed_current is not None and previous == "SETUP_ENTSTEHT":
                    confirmed_episodes.append(confirmed_current)
                    confirmed_current = None

            if raw == "SETUP_ENTSTEHT":
                if current is None or current["direction"] != direction or ts - current["last"] > 90:
                    if current:
                        episodes.append(current)
                    current = {"start": ts, "last": ts, "direction": direction, "rows": 0, "best_missing": missing, "met": Counter(), "missing": Counter()}
                current["last"] = ts
                current["rows"] += 1
                if len(missing) < len(current["best_missing"]):
                    current["best_missing"] = missing
                current["met"].update(key for key, value in conditions.items() if value)
                current["missing"].update(missing)
            elif current is not None and ts - current["last"] > 90:
                episodes.append(current)
                current = None
    if current:
        episodes.append(current)
    if confirmed_current:
        confirmed_episodes.append(confirmed_current)
    if machine is not None:
        episodes = confirmed_episodes

    thresholds = (25, 50, 75, 100, 150, 200)
    outcome_counts = Counter()
    rows_out = []
    for idx, episode in enumerate(episodes, 1):
        missing = episode["best_missing"]
        missing_counts[len(missing)] += 1
        if len(missing) == 1:
            only_missing[missing[0]] += 1
        entry_i = bisect.bisect_left(tick_times, episode["start"])
        outcome = None
        if entry_i < len(ticks):
            _, bid, ask = ticks[entry_i]
            entry = ask if episode["direction"] == "LONG" else bid
            finish = episode["start"] + 300
            right = bisect.bisect_right(tick_times, finish)
            path = ticks[entry_i:right]
            complete = bool(path and tick_times[-1] >= finish)
            pnl = [(future_bid - entry) if episode["direction"] == "LONG" else (entry - future_ask) for _, future_bid, future_ask in path]
            if pnl:
                outcome = {"entry": entry, "mfe": max(pnl), "mae": min(pnl), "complete_5m": complete}
                for target in thresholds:
                    hit = complete and max(pnl) >= target
                    outcome[f"hit_{target}"] = hit if complete else None
                    if hit:
                        outcome_counts[target] += 1
        rows_out.append({
            "setup_id": f"20260825-{idx:03d}",
            "start": datetime.fromtimestamp(episode["start"], UTC).isoformat(),
            "end": datetime.fromtimestamp(episode["last"], UTC).isoformat(),
            "duration_s": round(episode["last"] - episode["start"], 3),
            "direction": episode["direction"],
            "evaluations": episode["rows"],
            "best_missing": missing,
            "outcome": outcome,
        })

    result = {
        "window": {"start": args.start, "end": args.end},
        "vantage_ticks": len(ticks),
        "vantage_first": datetime.fromtimestamp(ticks[0][0], UTC).isoformat() if ticks else None,
        "vantage_last": datetime.fromtimestamp(ticks[-1][0], UTC).isoformat() if ticks else None,
        "evaluations": evaluations,
        "directions": directions,
        "raw_state_evaluations": raw_counts,
        "episodes": [] if args.summary_only else rows_out,
        "episode_count": len(rows_out),
        "missing_condition_buckets": missing_counts,
        "only_missing": only_missing,
        "complete_5m_episodes": sum(bool(row["outcome"] and row["outcome"]["complete_5m"]) for row in rows_out),
        "target_hits_5m": outcome_counts,
    }
    print(json.dumps(result, indent=2, default=dict))


if __name__ == "__main__":
    main()
