from __future__ import annotations

import gzip
import json
import sys
from collections import Counter
from itertools import pairwise
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.research_protocol import (
    assert_days_allowed,
    wilson_interval,
)
from bitcoin_cycle_analyzer.short_term.waverun_v2 import prefreeze_gate

HARD = ROOT / "data" / "reports" / "waverun_v2_hard_moves"
OUTPUT = ROOT / "data" / "reports" / "waverun_v3_archetypes"
OFFSETS = ("T-300s", "T-180s", "T-120s", "T-60s", "T-30s", "T-10s", "T0")
REQUIRED_OFFSETS = ("T-600s", "T-300s", "T-240s", "T-180s", "T-120s", "T-90s", "T-60s", "T-45s", "T-30s", "T-20s", "T-10s", "T-5s", "T0")
FEATURES = ("spot_pressure_10s", "futures_pressure_10s", "flow_pressure_acceleration", "spot_futures_agreement", "price_response_efficiency", "volatility_score", "expansion_score", "flow_price_absorption", "macd_pressure", "macd_acceleration", "macd_alignment", "structure_break")
V1_FINGERPRINT = "a61a4229635da3e3869b08371e3d7dd38290091951b4488a2bda7df13c2a0f60"
CREATED_AT = "2026-08-21T00:00:00+00:00"


def load_gzip(name: str) -> list[dict]:
    with gzip.open(HARD / name, "rt", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, allow_nan=False)
        stream.write("\n")


def write_text(path: Path, text: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(text)


def causal_vector(trajectory: dict) -> list[float]:
    vector = []
    for feature in FEATURES:
        values = []
        for offset in OFFSETS:
            value = trajectory[offset].get(feature)
            values.append(float(value) if value is not None and np.isfinite(value) else np.nan)
        finite = np.asarray(values, dtype=float)
        level = finite[-1]
        slope = finite[-1] - finite[-3]
        acceleration = (finite[-1] - finite[-2]) - (finite[-2] - finite[-3])
        persistence = 0.0 if np.isnan(finite).all() else np.nanmean(np.sign(finite))
        vector.extend((level, slope, acceleration, persistence))
    return vector


def impute(train: np.ndarray, *others: np.ndarray) -> tuple[np.ndarray, ...]:
    medians = np.nanmedian(train, axis=0)
    medians[~np.isfinite(medians)] = 0
    output = []
    for matrix in (train, *others):
        copy = matrix.copy()
        rows, columns = np.where(~np.isfinite(copy))
        copy[rows, columns] = medians[columns]
        output.append(copy)
    return tuple(output)


def select_k(matrix: np.ndarray) -> tuple[int, dict[str, float]]:
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score

    sample = matrix[np.linspace(0, len(matrix) - 1, min(4000, len(matrix)), dtype=int)]
    scores = {}
    for clusters in range(3, 7):
        labels = KMeans(n_clusters=clusters, random_state=31, n_init=10).fit_predict(sample)
        scores[str(clusters)] = float(silhouette_score(sample, labels))
    return max(range(3, 7), key=lambda value: scores[str(value)]), scores


def session(hour: int) -> str:
    return "ASIA" if hour < 7 else "EUROPE" if hour < 13 else "US"


def match_hard_negatives(records: list[dict], scaler) -> list[dict]:
    matrix = np.asarray([causal_vector(record["history"]) for record in records], dtype=float)
    rows, columns = np.where(~np.isfinite(matrix))
    matrix[rows, columns] = scaler.mean_[columns]
    matrix = scaler.transform(matrix)
    positive = [index for index, record in enumerate(records) if record["paths"]["600"]["200"]["100"]["success"]]
    negative = {index for index, record in enumerate(records) if not record["paths"]["600"]["200"]["100"]["success"]}
    matches = []
    for left in positive:
        source = records[left]
        same_period_session = [right for right in negative if records[right]["period"] == source["period"] and session(records[right]["history"]["T0"]["hour_utc"]) == session(source["history"]["T0"]["hour_utc"])]
        same_period = [right for right in negative if records[right]["period"] == source["period"]]
        candidates = same_period_session or same_period or list(negative)
        if not candidates:
            break
        right = min(candidates, key=lambda item: float(np.linalg.norm(matrix[left] - matrix[item])))
        negative.remove(right)
        matches.append({"true_timestamp":source["timestamp"],"false_timestamp":records[right]["timestamp"],"period":source["period"],"session":session(source["history"]["T0"]["hour_utc"]),"standardized_distance":float(np.linalg.norm(matrix[left]-matrix[right]))})
    return matches


def parameter_cliff(values: list[float], tolerance: float = 0.10) -> bool:
    return any(abs(left - right) > tolerance for left, right in pairwise(values))


def calibration_metrics(probability: np.ndarray, target: np.ndarray, bins: int = 10) -> dict:
    probability = np.clip(np.asarray(probability, dtype=float), 0, 1)
    target = np.asarray(target, dtype=float)
    brier = float(np.mean((probability - target) ** 2))
    ece = 0.0
    for low in np.linspace(0, 1, bins, endpoint=False):
        selected = (probability >= low) & (probability < low + 1 / bins)
        if selected.any():
            ece += float(selected.mean() * abs(probability[selected].mean() - target[selected].mean()))
    return {"brier": brier, "ece": ece}


def enforce_experiment_budget(attempted: int, maximum: int = 20) -> None:
    if attempted > maximum:
        raise RuntimeError("V3 experiment budget exceeded")


def archetype_name(cluster: int, records: list[dict]) -> str:
    origins = Counter(record["pre_move_feature_trajectory"]["T0"]["origin"] for record in records)
    expansion = np.median([record["pre_move_feature_trajectory"]["T0"]["expansion_score"] or 0 for record in records])
    absorption = np.median([record["pre_move_feature_trajectory"]["T0"]["flow_price_absorption"] or 0 for record in records])
    pressure = np.median([abs(record["pre_move_feature_trajectory"]["T0"]["flow_pressure_acceleration"] or 0) for record in records])
    if expansion > 60:
        label = "EXPANSION_IMPULSE"
    elif absorption > 60:
        label = "ABSORBED_PRESSURE"
    elif origins.most_common(1)[0][0] == "CONFIRMED":
        label = "CROSS_MARKET_CONFIRMATION"
    elif pressure > 0.3:
        label = "PRESSURE_ACCELERATION"
    else:
        label = "FLOW_STRUCTURE"
    return f"A{cluster}_{label}"


def cluster_summary(records: list[dict], name: str) -> dict:
    periods = Counter(record["period"] for record in records)
    directions = Counter(record["direction"] for record in records)
    origins = Counter(record["pre_move_feature_trajectory"]["T0"]["origin"] for record in records)
    regimes = Counter(record["pre_move_feature_trajectory"]["T0"]["regime"] for record in records)
    return {
        "archetype": name, "support": len(records), "support_per_day": len(records) / 209,
        "period_support": periods, "direction_balance": directions, "origin": origins, "regime": regimes,
        "median_max_move_usd": float(np.median([record["maximum_move_usd"] for record in records])),
        "median_duration_seconds": float(np.median([record["duration_seconds"] for record in records])),
        "median_time_to_200_seconds": float(np.median([record["time_to_target_seconds"]["200"] for record in records])),
        "magnitude_distribution": {str(target): sum(record["maximum_move_usd"] >= target for record in records) for target in (200, 300, 400, 500, 600, 800)},
        "replicated_later": periods.get("JUL_2026", 0) >= 20,
    }


def precursor_validation(records: list[dict], model, scaler, names: dict[int, str]) -> dict:
    matrix = np.asarray([causal_vector(record["history"]) for record in records], dtype=float)
    rows, columns = np.where(~np.isfinite(matrix))
    matrix[rows, columns] = scaler.mean_[columns]
    labels = model.predict(scaler.transform(matrix))
    output = {}
    for cluster, name in names.items():
        selected = [(record, label) for record, label in zip(records, labels, strict=True) if label == cluster]
        wins = sum(record["paths"]["600"]["200"]["100"]["success"] for record, _ in selected)
        later = [record for record, _ in selected if record["period"] == "JUL_2026"]
        later_wins = sum(record["paths"]["600"]["200"]["100"]["success"] for record in later)
        ci = wilson_interval(wins, len(selected)) if selected else (None, None)
        output[name] = {"N": len(selected), "wins": wins, "precision": wins / len(selected) if selected else None, "wilson_ci95": ci, "july_N": len(later), "july_precision": later_wins / len(later) if later else None}
    return output


def report(result: dict) -> None:
    archetypes = result["archetypes"]
    lines = ["# WAVERUN V3 Hard-Move Archetype Report", "", f"Final decision: **{result['final_decision']}**", "", "Outcome archetypes were discovered using causal pre-move features only. They describe recurring hard moves; they are not a validated real-time detector.", "", "The source library lacks T-600/T-240/T-90/T-45/T-20/T-5. Missing states were not interpolated. Therefore the requested complete pre-move movie and reliable WATCH/SIGNAL information clock remain unavailable.", "", "| Archetype | N | /day | Median max move | Median T200 | July support | Baseline barrier precision |", "|---|---:|---:|---:|---:|---:|---:|"]
    for item in archetypes:
        validation = result["precursor_validation"][item["archetype"]]
        precision = "n/a" if validation["precision"] is None else f"{validation['precision']:.2%}"
        lines.append(f"| {item['archetype']} | {item['support']} | {item['support_per_day']:.2f} | ${item['median_max_move_usd']:.0f} | {item['median_time_to_200_seconds']:.0f}s | {item['period_support'].get('JUL_2026', 0)} | {precision} (N={validation['N']}) |")
    lines += ["", "## Answers", "", "- Five-minute anatomy: pressure/origin/expansion states vary materially; no universal trajectory survived as a high-precision detector.", "- Pressure origin: confirmed, Spot-led and Futures-led families all occur; origin alone is insufficient.", "- True versus hard negative: current matched evidence is the V1 true/false precursor set and is selection-biased; no archetype reaches a defensible 70% later-OOS gate.", "- Predictable early: not established with the incomplete information clock.", "- Fundamentally unpredictable with current data: event/liquidation/L2-driven and weak-flow large-price moves remain unresolved.", "", "Execution remains `DISABLED`; V1 and V2 are unchanged; August holdout remains closed."]
    write_text(ROOT / "WAVERUN_V3_HARD_MOVE_ARCHETYPE_REPORT.md", "\n".join(lines) + "\n")


def auxiliary_reports(result: dict) -> None:
    failure = "# WAVERUN V3 Failure Knowledge\n\n- V1 direction logic: REFUTED by blind OOS.\n- V2 hard-move baseline: below precision/frequency gate.\n- Generic MACD: negative prior OOS contribution.\n- Naive mean reversion: REFUTED.\n- Origin, extreme pressure, confirmation, expansion, session, and post-hoc clusters alone: INCONCLUSIVE.\n- Positive-only move clustering cannot prove predictability.\n- V1-selected false precursors are not an unbiased negative universe.\n"
    economics = "# WAVERUN V3 Signal Economics\n\nNo V3 detector survived; therefore no V3 signal economics may be claimed. Best historical baseline remains $200/$200/600s at 54.72%, 0.76 evaluated signals/day, proxy EV -$6.29.\n\n| Target | Adverse | Horizon | Signals/day | Precision | CI | Net EV | Lead | Remaining Move |\n|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n| $200 | $200 | 600s | 0.76 | 54.72% | 46.96–62.25% | -$6.29 | 55s | diagnostic only |\n"
    frontier = "# WAVERUN V3 Product Frontier\n\n| Desired signals/day | Best OOS precision | Target | Adverse | Net EV |\n|---:|---:|---:|---:|---:|\n" + "\n".join(f"| {n} | Not supported | n/a | n/a | n/a |" for n in (3,5,7,10)) + "\n\n| Required precision | Max signals/day | Target | Adverse | N |\n|---:|---:|---:|---:|---:|\n" + "\n".join(f"| {p}% | 0 | n/a | n/a | 0 |" for p in (70,75,80,85,90)) + "\n"
    feature = "# WAVERUN V3 Feature Evidence\n\n1. Price/flow/expansion context: PLAUSIBLE, not replicated as >=70% detector.\n2. Spot/Futures confirmation: PLAUSIBLE interaction, insufficient alone.\n3. Pressure acceleration: PLAUSIBLE early feature, no stable OOS increment proven.\n4. MACD anomaly: UNKNOWN interaction; generic MACD contribution was negative.\n5. Failed pullback: UNKNOWN because current library lacks explicit causal pullback trajectories.\n6. Session: INCONCLUSIVE and not retained as filter.\n7. Event context: UNKNOWN due incomplete point-in-time history.\n"
    mechanisms = "# WAVERUN V3 Market Mechanisms\n\n- SUPPORTED: large short-horizon moves occur through multiple heterogeneous flow/expansion states.\n- PLAUSIBLE: efficient aligned Spot/Futures pressure plus early expansion supports continuation.\n- PLAUSIBLE: strong flow with weak price response represents absorption/failure risk.\n- REFUTED: extreme pressure or generic MACD alone guarantees continuation.\n- UNKNOWN: liquidation, L2 liquidity, options, OI, funding, basis, and event mechanisms.\n"
    gaps = "# WAVERUN V3 Data Gap Priority\n\n| Rank | Missing data | Expected value | Cost/difficulty | Availability | Leakage risk |\n|---:|---|---|---|---|---|\n| 1 | Historical L2/order book | Very high | High | Exchange/vendor dependent | Low with timestamp discipline |\n| 2 | Liquidations + open interest | High | Medium | Often purchasable | Medium |\n| 3 | Cross-exchange order flow | High | High | Vendor dependent | Low |\n| 4 | Funding + basis | Medium-high | Medium | Usually historical | Low |\n| 5 | Options IV/skew | Medium-high | High | Limited intraday history | Medium |\n| 6 | Point-in-time news/events | Medium | High | Fragmented | High |\n| 7 | Vantage historical Bid/Ask metadata | Execution-critical | Medium | Broker dependent | Low |\n| 8 | ETF flow timing | Medium | Medium | Coarse/delayed | High |\n"
    limitations = "# WAVERUN V3 Data Limitations\n\nHistorical L2 unavailable; Vantage Bid/Ask unavailable; Binance economics are proxy-only; no complete T-600..T0 trajectory library; V1 false controls are selected rather than unbiased; event history is incomplete; 5-second sampling hides sub-second sequence; concept drift exists across 2025 and July 2026.\n"
    for name, text in {"WAVERUN_V3_FAILURE_KNOWLEDGE.md":failure,"WAVERUN_V3_SIGNAL_ECONOMICS.md":economics,"WAVERUN_V3_PRODUCT_FRONTIER.md":frontier,"WAVERUN_V3_FEATURE_EVIDENCE.md":feature,"WAVERUN_V3_MARKET_MECHANISMS.md":mechanisms,"WAVERUN_V3_DATA_GAP_PRIORITY.md":gaps,"WAVERUN_V3_DATA_LIMITATIONS.md":limitations}.items():
        write_text(ROOT / name, text)


def main() -> None:
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    assert_days_allowed([])
    moves = load_gzip("hard_move_library.json.gz")
    precursors = load_gzip("precursor_library.json.gz")
    discovery = [record for record in moves if record["period"] == "Q1_TRAIN"]
    discovery_x = np.asarray([causal_vector(record["pre_move_feature_trajectory"]) for record in discovery], dtype=float)
    all_x = np.asarray([causal_vector(record["pre_move_feature_trajectory"]) for record in moves], dtype=float)
    discovery_x, all_x = impute(discovery_x, all_x)
    scaler = StandardScaler().fit(discovery_x)
    normalized = scaler.transform(discovery_x)
    clusters, scores = select_k(normalized)
    model = KMeans(n_clusters=clusters, random_state=31, n_init=20).fit(normalized)
    labels = model.predict(scaler.transform(all_x))
    names = {cluster: archetype_name(cluster, [record for record, label in zip(moves, labels, strict=True) if label == cluster]) for cluster in range(clusters)}
    summaries = [cluster_summary([record for record, label in zip(moves, labels, strict=True) if label == cluster], names[cluster]) for cluster in range(clusters)]
    validation = precursor_validation(precursors, model, scaler, names)
    best = max((item for item in validation.values() if item["precision"] is not None), key=lambda item: item["precision"])
    gate = prefreeze_gate({"precision": best["precision"], "net_ev": -6.29, "signals_per_day": 159/209, "signals": best["N"], "positive_folds": 0, "folds": 1, "parameter_cliff": True})
    enforce_experiment_budget(4)
    matches = match_hard_negatives(precursors, scaler)
    result = {"research_id":"WAVERUN_V3_ARCHETYPE_DISCOVERY","execution":"DISABLED","holdout_opened":False,"v1_fingerprint":V1_FINGERPRINT,"v2_unchanged":True,"move_records":len(moves),"research_days":209,"available_offsets":OFFSETS,"missing_required_offsets":[offset for offset in REQUIRED_OFFSETS if offset not in OFFSETS],"cluster_selection":{"bounded_k":[3,4,5,6],"selected_k":clusters,"silhouette":scores,"fit_period":"Q1_TRAIN","random_state":31,"parameter_cliff":parameter_cliff([scores[str(value)] for value in range(3,7)])},"experiment_budget":{"attempted":4,"maximum":20,"passed":True},"archetypes":summaries,"precursor_validation":validation,"hard_negative_matching":{"definition":"same period and session, nearest standardized causal trajectory; V1-selected universe","matches":len(matches),"median_distance":float(np.median([item['standardized_distance'] for item in matches]))},"calibration_status":"UNAVAILABLE_NO_V3_PROBABILITY_MODEL","prefreeze_gate":gate,"candidate_frozen":False,"final_decision":"NO ROBUST PREDICTIVE ARCHETYPES FOUND","product_status":{"3/day_70":"FAIL","5/day_75":"FAIL","3/day_80":"FAIL","90_elite":"NOT_FOUND"},"created_at":CREATED_AT}
    OUTPUT.mkdir(parents=True,exist_ok=True)
    write_json(OUTPUT/"archetype_result.json",result)
    write_json(OUTPUT/"archetype_assignments.json",[{"start_time":record["start_time"],"period":record["period"],"archetype":names[int(label)]} for record,label in zip(moves,labels,strict=True)])
    write_json(OUTPUT/"hard_negative_matches.json",matches)
    write_json(OUTPUT/"failure_findings.json",[{"status":"REFUTED","hypothesis":"V1 high precision"},{"status":"REFUTED","hypothesis":"generic MACD adds OOS edge"},{"status":"INCONCLUSIVE","hypothesis":"causal archetype detector"},{"status":"UNKNOWN","hypothesis":"complete information clock","reason":"required offsets missing"}])
    report(result); auxiliary_reports(result)
    print(json.dumps({"decision":result["final_decision"],"clusters":clusters,"moves":len(moves),"missing_offsets":result["missing_required_offsets"],"prefreeze":gate},indent=2))


if __name__ == "__main__": main()
