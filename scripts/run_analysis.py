from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import OHLCVStore
from bitcoin_cycle_analyzer.analyzer import analyze
from bitcoin_cycle_analyzer.audit import save_analysis

config = load_config()
frame = OHLCVStore(config["data"]["database"]).load("1d")
if frame.empty:
    raise SystemExit("No daily data. Run scripts/update_data.py first.")
result = analyze(frame, config)
payload = {key: value for key, value in result.items() if key not in {"data", "swings", "similar_cases"}}
payload["score"] = vars(result["score"])
payload["parameters_version"] = config["version"]
payload["data_range"] = {"from": frame.index.min(), "to": frame.index.max(), "rows": len(frame)}
path = save_analysis(payload)
print(json.dumps({"price": result["price"], "score": result["score"].total, "classification": result["score"].classification, "states": result["states"], "audit_file": str(path)}, indent=2, ensure_ascii=False))

