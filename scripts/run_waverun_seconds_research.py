from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

HORIZONS = (10, 20, 30, 45, 60, 90, 120, 180, 300)
REACTION_DELAYS = (0, 1, 2, 3, 5, 10)
SIGNAL_THRESHOLD = 0.0002


def _load(day: date) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    raw = ROOT / "runtime" / "waverun_data" / "raw"
    relative = Path(f"{day:%Y}") / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"
    vantage = pd.read_parquet(raw / "vantage" / "BTCUSD" / relative, columns=["timestamp", "bid", "ask"]).sort_values("timestamp")
    exchanges = {}
    for name in ("binance_spot", "binance_futures"):
        exchanges[name] = pd.read_parquet(raw / name / "BTCUSDT" / relative,
                                          columns=["exchange_timestamp", "price", "quantity", "buyer_is_maker"]).sort_values("exchange_timestamp")
    return vantage, exchanges


def _second_quotes(vantage: pd.DataFrame) -> pd.DataFrame:
    frame = vantage.set_index("timestamp")[["bid", "ask"]].resample("1s").last().ffill()
    frame["mid"] = (frame.bid + frame.ask) / 2
    frame["return_30s"] = frame.mid / frame.mid.shift(30) - 1
    frame["return_60s"] = frame.mid / frame.mid.shift(60) - 1
    frame["rolling_vol"] = frame.mid.pct_change().rolling(300, min_periods=60).std()
    frame["zscore_30s"] = frame.return_30s / frame.rolling_vol.replace(0, np.nan)
    return frame.dropna(subset=["bid", "ask", "mid"])


def _second_trades(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.set_index("exchange_timestamp")
    grouped = frame.resample("1s").agg(price=("price", "last"), quantity=("quantity", "sum"))
    grouped["buy_quantity"] = frame["quantity"].where(~frame.buyer_is_maker, 0).resample("1s").sum()
    grouped["sell_quantity"] = frame["quantity"].where(frame.buyer_is_maker, 0).resample("1s").sum()
    grouped["delta"] = grouped.buy_quantity - grouped.sell_quantity
    grouped["return_1s"] = grouped.price / grouped.price.shift(1) - 1
    return grouped.dropna(subset=["price"])


def _quote_index(quotes: pd.DataFrame) -> tuple[np.ndarray, pd.DataFrame]:
    return quotes.index, quotes


def _trade_paths(quotes: pd.DataFrame, directions: np.ndarray, signal_times: pd.DatetimeIndex, horizon: int, delay: int) -> tuple[list[float], list[float]]:
    index, frame = _quote_index(quotes)
    entry_targets = signal_times + pd.Timedelta(seconds=delay)
    entry_pos = index.searchsorted(entry_targets, side="left")
    valid = entry_pos < len(frame)
    if not valid.any():
        return [], []
    valid_positions = entry_pos[valid]
    exit_targets = index.take(valid_positions) + pd.Timedelta(seconds=horizon)
    exit_pos = index.searchsorted(exit_targets, side="left")
    valid_exit = exit_pos < len(frame)
    if not valid_exit.any():
        return [], []
    valid_positions = valid_positions[valid_exit]
    exit_pos = exit_pos[valid_exit]
    valid_directions = directions[valid][valid_exit]
    ask = frame.ask.to_numpy()[valid_positions]
    bid = frame.bid.to_numpy()[valid_positions]
    exit_bid = frame.bid.to_numpy()[exit_pos]
    exit_ask = frame.ask.to_numpy()[exit_pos]
    values = np.where(valid_directions > 0, exit_bid / ask - 1, bid / exit_ask - 1)
    entry_mid = (bid + ask) / 2
    exit_mid = (exit_bid + exit_ask) / 2
    gross = np.where(valid_directions > 0, exit_mid / entry_mid - 1, entry_mid / exit_mid - 1)
    return values.astype(float).tolist(), gross.astype(float).tolist()


def lead_lag(quotes: pd.DataFrame, trades: pd.DataFrame, source: str) -> list[dict]:
    results = []
    signals = trades[trades.return_1s.abs() >= SIGNAL_THRESHOLD]
    for horizon in HORIZONS:
        for delay in REACTION_DELAYS:
            directions = np.where(signals.return_1s.to_numpy() > 0, 1, -1)
            outcomes, gross = _trade_paths(quotes, directions, signals.index, horizon, delay)
            results.append({"study": "cross_exchange_event", "source": source, "horizon_seconds": horizon, "reaction_delay_seconds": delay, "samples": len(outcomes), "directional_consistency": None if not gross else float(sum(x > 0 for x in gross) / len(gross)), "net_positive_rate": None if not outcomes else float(sum(x > 0 for x in outcomes) / len(outcomes)), "net_ev": None if not outcomes else float(np.mean(outcomes)), "signal_threshold": SIGNAL_THRESHOLD, "execution": "DISABLED"})
    return results


def mean_reversion(quotes: pd.DataFrame) -> list[dict]:
    results = []
    signals = quotes[(quotes.zscore_30s >= 2) | (quotes.zscore_30s <= -2)]
    for horizon in HORIZONS:
        for delay in REACTION_DELAYS:
            directions = np.where(signals.zscore_30s.to_numpy() > 0, -1, 1)
            outcomes, _ = _trade_paths(quotes, directions, signals.index, horizon, delay)
            results.append({"study": "vantage_mean_reversion", "horizon_seconds": horizon, "reaction_delay_seconds": delay, "samples": len(outcomes), "net_ev": None if not outcomes else float(np.mean(outcomes)), "gross_positive_rate": None if not outcomes else float(sum(x > 0 for x in outcomes) / len(outcomes)), "signal": "30s_return_zscore_2", "execution": "DISABLED"})
    return results


def _aggregate(rows: list[dict]) -> list[dict]:
    if not rows:
        return []
    keys = [key for key in rows[0] if key not in {"samples", "directional_consistency", "net_positive_rate", "net_ev", "gross_positive_rate"}]
    grouped: dict[tuple, list[dict]] = {}
    for row in rows:
        grouped.setdefault(tuple(row.get(key) for key in keys), []).append(row)
    output = []
    for identity, items in grouped.items():
        result = dict(zip(keys, identity, strict=True))
        result["samples"] = sum(item["samples"] for item in items)
        for metric in ("directional_consistency", "net_positive_rate", "net_ev", "gross_positive_rate"):
            usable = [(item[metric], item["samples"]) for item in items if item.get(metric) is not None and item["samples"]]
            if usable:
                result[metric] = sum(value * samples for value, samples in usable) / sum(samples for _, samples in usable)
        output.append(result)
    return output


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=offset) for offset in range((end - start).days + 1)]


def main() -> None:
    splits = {"train": _days(date(2026, 7, 20), date(2026, 8, 6)),
              "validation": _days(date(2026, 8, 7), date(2026, 8, 11)),
              "walk_forward": _days(date(2026, 8, 12), date(2026, 8, 15))}
    results = {"execution": "DISABLED", "status": "RESEARCH_ONLY", "splits": {},
               "final_holdout": ["2026-08-16", "2026-08-17"], "excluded_exploratory": ["2026-08-18"],
               "limitations": ["Final holdout is not opened by this baseline run.", "Binance historical L2 and liquidation history are unavailable.", "No champion selection is performed."]}
    total_vantage = 0
    for split, days in splits.items():
        split_result = {"days": [day.isoformat() for day in days], "vantage_rows": 0, "vantage_seconds": 0,
                        "binance": {source: {"rows": 0, "seconds": 0, "lead_lag": []} for source in ("binance_spot", "binance_futures")},
                        "mean_reversion": []}
        for day in days:
            vantage, exchanges = _load(day)
            quotes = _second_quotes(vantage)
            split_result["vantage_rows"] += len(vantage)
            split_result["vantage_seconds"] += len(quotes)
            split_result["mean_reversion"].extend(mean_reversion(quotes))
            for source, frame in exchanges.items():
                trades = _second_trades(frame)
                split_result["binance"][source]["rows"] += len(frame)
                split_result["binance"][source]["seconds"] += len(trades)
                split_result["binance"][source]["lead_lag"].extend(lead_lag(quotes, trades, source))
        split_result["mean_reversion"] = _aggregate(split_result["mean_reversion"])
        for source in split_result["binance"]:
            split_result["binance"][source]["lead_lag"] = _aggregate(split_result["binance"][source]["lead_lag"])
        results["splits"][split] = split_result
        total_vantage += split_result["vantage_rows"]
    output = ROOT / "data" / "reports" / "waverun_seconds_research.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, indent=2), encoding="utf-8")
    summary = ["# WAVERUN Seconds Research", "", "Status: `RESEARCH_ONLY` / `execution: DISABLED`", "", f"Vantage ticks in Train/Validation/Walk-forward: **{total_vantage:,}**", "", "The 2026-08-16..17 final holdout remains unopened. The previously inspected 2026-08-18 day is excluded.", "", "No edge conclusion is promoted. Results use Vantage Bid/Ask execution and fixed predeclared horizons/reaction delays.", "", f"Machine-readable result: `{output.relative_to(ROOT)}`", ""]
    (ROOT / "WAVERUN_SECONDS_RESEARCH_REPORT.md").write_text("\n".join(summary), encoding="utf-8")
    print(json.dumps({"status": results["status"], "vantage_ticks": total_vantage, "splits": list(splits), "output": str(output), "execution": "DISABLED"}))


if __name__ == "__main__":
    main()
