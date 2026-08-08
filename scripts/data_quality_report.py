from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.data_quality import quality_report

config = load_config()
store = OHLCVStore(config["data"]["database"])
reports = {}
for timeframe in config["data"]["timeframes"]:
    frame = store.load_canonical(timeframe)
    reports[timeframe] = quality_report(frame, timeframe)
target = Path("data/reports/data_quality.json")
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps({tf: {"rows": report["rows"], "critical": report["critical_issue_count"], "missing_periods": len(report["issues"]["missing_periods"])} for tf, report in reports.items()}, indent=2))
