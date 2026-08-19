from __future__ import annotations

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bitcoin_cycle_analyzer.short_term.pressure import macd_features, robust_score
from bitcoin_cycle_analyzer.short_term.research_protocol import (
    EXPLORATORY,
    assert_days_allowed,
)

HORIZONS = (10, 20, 30, 45, 60, 90, 120, 180, 240, 300)
REACTION_DELAYS = (0, 1, 2, 3, 5, 10)
MACD_HORIZONS = (10, 30, 60, 180, 300, 900)
RAW = ROOT / "runtime" / "waverun_data" / "raw"
DERIVED = ROOT / "runtime" / "waverun_data" / "derived" / "research"


def _partition(source: str, symbol: str, day: date) -> Path:
    return RAW / source / symbol / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"


def _quotes(day: date) -> pd.DataFrame:
    frame = pd.read_parquet(_partition("vantage", "BTCUSD", day), columns=["timestamp", "bid", "ask"])
    quotes = frame.set_index("timestamp").sort_index().resample("1s").last().ffill()
    quotes["mid"] = (quotes.bid + quotes.ask) / 2
    quotes["spread"] = quotes.ask - quotes.bid
    quotes["spread_pct"] = quotes.spread / quotes.mid
    return quotes


def _flow(day: date, source: str) -> pd.DataFrame:
    frame = pd.read_parquet(_partition(source, "BTCUSDT", day),
                            columns=["exchange_timestamp", "price", "quantity", "buyer_is_maker"])
    frame["second"] = frame.exchange_timestamp.dt.floor("s")
    frame["buy_volume"] = frame.quantity.where(~frame.buyer_is_maker, 0.0)
    frame["sell_volume"] = frame.quantity.where(frame.buyer_is_maker, 0.0)
    grouped = frame.groupby("second", sort=True).agg(
        exchange_price=("price", "last"), volume=("quantity", "sum"), buy_volume=("buy_volume", "sum"),
        sell_volume=("sell_volume", "sum"), trades=("price", "size"),
    )
    grouped["delta"] = grouped.buy_volume - grouped.sell_volume
    grouped["normalized_delta"] = grouped.delta / grouped.volume.replace(0, np.nan)
    grouped["cvd"] = grouped.delta.cumsum()
    grouped["cvd_velocity"] = grouped.delta.rolling(10, min_periods=3).sum()
    grouped["cvd_acceleration"] = grouped.cvd_velocity.diff(5)
    grouped["trade_rate_acceleration"] = grouped.trades.diff(5)
    grouped["price_return"] = grouped.exchange_price.pct_change(5)
    return grouped


def _align_flow(index: pd.DatetimeIndex, flow: pd.DataFrame, prefix: str) -> pd.DataFrame:
    aligned = flow.reindex(index)
    aligned["exchange_price"] = aligned.exchange_price.ffill()
    for column in ("volume", "buy_volume", "sell_volume", "trades", "delta"):
        aligned[column] = aligned[column].fillna(0)
    for column in ("normalized_delta", "cvd_velocity", "cvd_acceleration", "trade_rate_acceleration", "price_return"):
        aligned[column] = aligned[column].fillna(0)
    aligned["cvd"] = aligned.cvd.ffill().fillna(0)
    aligned["pressure"] = (aligned.normalized_delta * 100).clip(-100, 100)
    aligned["pressure_velocity"] = aligned.pressure.diff(5)
    aligned["pressure_acceleration"] = aligned.pressure_velocity.diff(5)
    return aligned.add_prefix(f"{prefix}_")


def _features(day: date) -> pd.DataFrame:
    quotes = _quotes(day)
    result = quotes.copy()
    for seconds in (1, 5, 10, 30, 60, 180, 300):
        result[f"price_return_{seconds}s"] = result.mid.pct_change(seconds)
        result[f"price_acceleration_{seconds}s"] = result[f"price_return_{seconds}s"].diff(seconds)
        result[f"price_pressure_{seconds}s"] = robust_score(result[f"price_return_{seconds}s"], 300)
    result["price_pressure"] = (0.5 * result.price_pressure_10s + 0.3 * result.price_pressure_30s + 0.2 * result.price_pressure_60s)
    result["price_pressure_velocity"] = result.price_pressure.diff(5)
    result["price_pressure_acceleration"] = result.price_pressure_velocity.diff(5)

    spot = _align_flow(result.index, _flow(day, "binance_spot"), "spot")
    futures = _align_flow(result.index, _flow(day, "binance_futures"), "futures")
    result = result.join(spot).join(futures)
    result["source_agreement"] = np.sign(result.spot_pressure) * np.sign(result.futures_pressure)
    result["source_divergence"] = result.spot_pressure - result.futures_pressure
    result["flow_pressure"] = (result.spot_pressure + result.futures_pressure) / 2
    result["flow_efficiency"] = result.mid.pct_change(10) / (result.flow_pressure / 100).replace(0, np.nan)
    result["absorption"] = (robust_score(result.flow_pressure.abs(), 300).clip(0, 100) *
                            (1 - robust_score(result.mid.pct_change(10).abs(), 300).abs() / 100)).clip(0, 100)

    for seconds in MACD_HORIZONS:
        close = result.mid.resample(f"{seconds}s", label="right", closed="left").last().dropna()
        macd = macd_features(close).add_prefix(f"macd_{seconds}s_")
        result = result.join(macd.reindex(result.index).ffill())
    result = result.copy()
    result["macd_pressure"] = np.mean([robust_score(result[f"macd_{seconds}s_histogram"], 300) for seconds in (10, 30, 60)], axis=0)
    result["macd_alignment"] = sum(np.sign(result[f"macd_{seconds}s_histogram"]) for seconds in MACD_HORIZONS)
    result["macd_fast_turn"] = np.sign(result.macd_10s_histogram_slope) + np.sign(result.macd_30s_histogram_slope)

    rolling_mean = result.mid.rolling(300, min_periods=60).mean()
    rolling_std = result.mid.rolling(300, min_periods=60).std().replace(0, np.nan)
    result["mean_zscore"] = (result.mid - rolling_mean) / rolling_std
    result["mean_displacement"] = robust_score(result.mean_zscore.abs(), 300).clip(0, 100)
    result["exhaustion"] = ((100 - result.price_pressure.abs()) * 0.4 + result.absorption * 0.4 +
                            (100 - result.macd_pressure.abs()) * 0.2).clip(0, 100)
    result["structure_break"] = np.sign(result.mid - result.mid.rolling(60, min_periods=20).max().shift(1)).fillna(0)
    result["reversion_confirmation"] = ((np.sign(result.price_pressure_velocity) == -np.sign(result.mean_zscore)) &
                                         (np.sign(result.macd_fast_turn) == -np.sign(result.mean_zscore)) &
                                         (result.structure_break == -np.sign(result.mean_zscore))).astype(int)
    result["continuation_score"] = (result.price_pressure + result.macd_pressure + result.spot_pressure + result.futures_pressure) / 4
    result["reversion_score"] = np.sign(-result.mean_zscore) * (result.mean_displacement + result.exhaustion + result.absorption) / 3

    vol = result.mid.pct_change().rolling(300, min_periods=60).std()
    result["volatility"] = vol
    result["volatility_score"] = robust_score(vol, 900)
    trend = result.mid.pct_change(300)
    result["regime"] = np.select(
        [result.volatility_score < -40, result.volatility_score > 40, trend > vol * 3, trend < -vol * 3],
        ["COMPRESSION", "EXPANSION", "TREND_UP", "TREND_DOWN"], default="RANGE",
    )
    result["spread_regime"] = np.select(
        [result.spread <= result.spread.rolling(900, min_periods=60).quantile(0.75),
         result.spread <= result.spread.rolling(900, min_periods=60).quantile(0.95)],
        ["NORMAL", "ELEVATED"], default="EXTREME",
    )
    result["hour_utc"] = result.index.hour
    result["weekday"] = result.index.dayofweek
    result["session"] = np.select([result.hour_utc < 7, result.hour_utc < 13, result.hour_utc < 21],
                                   ["ASIA", "EUROPE", "US"], default="ASIA")
    return _labels(result.copy())


def _labels(frame: pd.DataFrame) -> pd.DataFrame:
    labels: dict[str, pd.Series] = {}
    for delay in REACTION_DELAYS:
        entry_ask = frame.ask.shift(-delay)
        entry_bid = frame.bid.shift(-delay)
        entry_mid = frame.mid.shift(-delay)
        for horizon in HORIZONS:
            exit_bid = frame.bid.shift(-(delay + horizon))
            exit_ask = frame.ask.shift(-(delay + horizon))
            exit_mid = frame.mid.shift(-(delay + horizon))
            labels[f"long_net_{horizon}s_d{delay}"] = exit_bid / entry_ask - 1
            labels[f"short_net_{horizon}s_d{delay}"] = entry_bid / exit_ask - 1
            labels[f"gross_return_{horizon}s_d{delay}"] = exit_mid / entry_mid - 1
    return pd.concat([frame, pd.DataFrame(labels, index=frame.index)], axis=1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build causal WAVERUN research features; holdout locked by default")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2026, 7, 20))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 8, 15))
    parser.add_argument("--sample-seconds", type=int, default=5)
    args = parser.parse_args()
    days = [args.start + timedelta(days=offset) for offset in range((args.end - args.start).days + 1)]
    assert_days_allowed(days)
    if EXPLORATORY.intersection(days):
        raise SystemExit("exploratory 2026-08-18 is excluded from model research")
    results = []
    for day in days:
        frame = _features(day).iloc[::args.sample_seconds].copy()
        frame.insert(0, "timestamp", frame.index)
        output = DERIVED / f"{day:%Y}" / f"{day:%m}" / f"{day:%Y-%m-%d}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(output, compression="zstd", index=False)
        results.append({"day": day.isoformat(), "rows": len(frame), "columns": len(frame.columns), "path": str(output)})
        print(json.dumps(results[-1]), flush=True)
    manifest = {"execution": "DISABLED", "sample_seconds": args.sample_seconds, "horizons": HORIZONS,
                "reaction_delays": REACTION_DELAYS, "macd_horizons": MACD_HORIZONS, "days": results,
                "final_holdout_loaded": False, "exploratory_loaded": False}
    (DERIVED / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
