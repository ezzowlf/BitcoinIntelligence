from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.data_quality import quality_report
from bitcoin_cycle_analyzer.historical_validation import validate

config = load_config()
store = OHLCVStore(config["data"]["database"])
daily = store.load_canonical("1d")
quality = quality_report(daily, "1d")
if quality["critical_issue_count"]:
    raise SystemExit(f"Backtest blocked: {quality['critical_issue_count']} critical data-quality issues")
report, scores = validate(daily[["open", "high", "low", "close", "volume"]], config)
report["data_quality"] = quality
target = Path("data/reports")
target.mkdir(parents=True, exist_ok=True)
(target / "real_validation.json").write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
scores.to_csv(target / "point_in_time_scores.csv")
print(json.dumps({"score_rows": len(scores), "from": str(scores.index.min()), "to": str(scores.index.max()), "threshold_signal_counts": {key: value["signal_count"] for key, value in report["thresholds"].items()}, "walk_forward_folds": len(report["walk_forward"])}, indent=2))
