"""Import public external metrics independently; one provider failure never aborts others."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import truststore

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.derivatives.providers import BinanceFuturesProvider
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain.coinmetrics_provider import CoinMetricsCommunityProvider


def main() -> dict:
    truststore.inject_into_ssl()
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config.yaml")
    store = ExternalMetricStore(root / config["data"]["external_database"])
    results = {}
    jobs = {
        "binance_funding": lambda: BinanceFuturesProvider().funding_history(),
        "binance_open_interest": lambda: BinanceFuturesProvider().recent_open_interest(),
        "coinmetrics_community": lambda: CoinMetricsCommunityProvider().fetch(),
    }
    for name, job in jobs.items():
        try:
            records = job()
            results[name] = {"status": "AVAILABLE", "records": store.upsert(records)}
        except Exception as exc:
            results[name] = {"status": "ERROR", "records": 0, "error": f"{type(exc).__name__}: {exc}"}
    results["coverage"] = store.coverage().to_dict(orient="records")
    report = root / "data" / "reports" / "external_data_health.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    return results


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))
