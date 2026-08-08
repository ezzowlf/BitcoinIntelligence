from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import pandas as pd
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.core.cycle_engine import market_regime_series
from bitcoin_cycle_analyzer.core.analyzer import analyze_intelligence, public_payload
from bitcoin_cycle_analyzer.seasonality.statistics import monthly_statistics, weekday_statistics
from bitcoin_cycle_analyzer.seasonality.event_windows import event_window_statistics
from bitcoin_cycle_analyzer.seasonality.calendar_effects import turn_of_month_statistics, quarter_statistics
from bitcoin_cycle_analyzer.validation.ablation import ablation_report
from bitcoin_cycle_analyzer.historical_validation import signal_rows, aggregate_signals


def causal_seasonality_scores(frame: pd.DataFrame, index: pd.DatetimeIndex) -> pd.Series:
    monthly = frame.resample("ME").agg({"open":"first","close":"last"}).dropna()
    monthly["return"] = monthly.close / monthly.open - 1
    values = []
    for date in index:
        history = monthly[(monthly.index < date.replace(day=1)) & (monthly.index.month == date.month)]["return"]
        if len(history) < 3:
            values.append(np.nan)
        else:
            score = 50 + float(history.median()) * 100 + (float((history > 0).mean()) - .5) * 40
            values.append(max(0, min(100, score)))
    return pd.Series(values, index=index, name="seasonality_score").ffill().fillna(50)


config = load_config()
store = OHLCVStore(config["data"]["database"])
daily = store.load("1d")
scores = pd.read_csv("data/reports/point_in_time_scores.csv", parse_dates=["date"]).set_index("date")
scores.index = pd.to_datetime(scores.index, utc=True)
regimes = market_regime_series(daily)
seasonality = causal_seasonality_scores(daily, scores.index)
proxy = scores.score * .9 + seasonality * .1
forward_365 = daily.close.shift(-365) / daily.close - 1
validation = {
    "cycle_snapshot": analyze_intelligence(daily, config),
    "monthly": monthly_statistics(daily, regimes=regimes),
    "weekday": weekday_statistics(daily),
    "turn_of_month": turn_of_month_statistics(daily),
    "quarter": quarter_statistics(daily),
    "events": {name: event_window_statistics(daily, name, regimes=regimes) for name in ("thanksgiving", "black_friday", "christmas", "new_year")},
    "ablation": ablation_report(proxy, {"seasonality": seasonality * .1}, forward_365.reindex(proxy.index)),
    "unavailable_ablations": {name: "UNAVAILABLE: no verified point-in-time history" for name in ("onchain", "etf", "derivatives", "macro", "news")},
    "walk_forward": [],
}
folds = [("2016-07-09","2020-05-11"),("2020-05-11","2024-04-20"),("2024-04-20","2026-08-08")]
for number, (start, end) in enumerate(folds, 1):
    mask = (scores.index >= pd.Timestamp(start, tz="UTC")) & (scores.index < pd.Timestamp(end, tz="UTC"))
    technical_frame = pd.DataFrame({"score": scores.loc[mask,"score"], "price": scores.loc[mask,"price"]})
    proxy_frame = pd.DataFrame({"score": proxy.loc[mask], "price": scores.loc[mask,"price"]})
    validation["walk_forward"].append({"fold":number,"period":[start,end],"technical":aggregate_signals(signal_rows(daily,technical_frame,75)),"with_seasonality_proxy":aggregate_signals(signal_rows(daily,proxy_frame,75))})
target = Path("data/reports/intelligence_validation.json")
target.write_text(json.dumps(validation, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
snapshot = validation["cycle_snapshot"]
Path("data/reports/current_market_state.json").write_text(json.dumps(snapshot, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
Path("data/reports/public_market_state.json").write_text(json.dumps(public_payload(snapshot), indent=2, ensure_ascii=False, default=str), encoding="utf-8")
print(json.dumps({"cycle":snapshot["cycle"]["primary_regime"],"cycle_confidence":snapshot["cycle"]["primary_confidence"],"opportunity":snapshot["dimensions"]["long_term_value"],"timing":snapshot["entry_timing"],"evidence":snapshot["dimensions"]["evidence"],"seasonality":snapshot["dimensions"]["seasonality"],"ablation":validation["ablation"],"walk_forward_folds":len(validation["walk_forward"])}, indent=2))
