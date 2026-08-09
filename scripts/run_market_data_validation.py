"""Coverage-aware, point-in-time validation of external market factors."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.derivatives import analyze_derivatives


def rank_corr(left: pd.Series, right: pd.Series) -> float | None:
    joined = pd.concat([left, right], axis=1).dropna()
    return None if len(joined) < 30 else float(joined.rank().corr().iloc[0, 1])


def main() -> dict:
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config.yaml")
    prices = OHLCVStore(root / config["data"]["database"]).load("1d")
    prices.index = pd.to_datetime(prices.index, utc=True)
    store = ExternalMetricStore(root / config["data"]["external_database"])
    funding = store.load("funding_rate_8h")
    oi = store.load("open_interest_usd")
    daily_funding = funding.set_index("available_at").value.resample("1D").mean()
    history = pd.DataFrame({"close": prices.close, "funding": daily_funding}).dropna()
    history["funding_30d_z"] = (history.funding - history.funding.rolling(30).mean()) / history.funding.rolling(30).std()
    horizons = [7, 30, 90, 180, 365]
    validation = {}
    split = history.index[int(len(history) * .7)] if len(history) else None
    for days in horizons:
        target = history.close.shift(-days) / history.close - 1
        all_corr = rank_corr(-history.funding_30d_z, target)
        oos_corr = rank_corr(-history.loc[split:, "funding_30d_z"], target.loc[split:]) if split is not None else None
        validation[str(days)] = {"rank_correlation_all": all_corr, "rank_correlation_oos": oos_corr,
                                 "oos_start": None if split is None else str(split),
                                 "observations": int(pd.concat([history.funding_30d_z, target], axis=1).dropna().shape[0])}
    current = analyze_derivatives(prices.index[-1] + pd.Timedelta(days=2), funding=funding, open_interest=oi)
    report = {"method": "Fixed contrarian funding z-score; no weight optimization; 70/30 chronological OOS split",
              "causality": "Factors are joined by available_at, never event_timestamp alone.",
              "funding_validation": validation, "current_derivatives": current,
              "coverage": store.coverage().to_dict(orient="records"),
              "unavailable": {"etf": "No verified point-in-time provider configured",
                              "macro": "FRED_API_KEY absent; vintage-aware provider implemented but not run",
                              "news": "No MeanPulse news endpoint configured",
                              "onchain_historical_mvrv": "Community snapshot has no per-observation status-time; current/research only"},
              "limitations": ["Binance OI endpoint supplies only a recent rolling window.",
                              "Correlation is descriptive and not a calibrated probability.",
                              "Provider-specific exchange history can change with address attribution revisions."]}
    output = root / "data" / "reports" / "real_market_data_validation.json"
    output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
