"""Import public external metrics independently; one provider failure never aborts others."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import truststore
import os

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.derivatives.providers import BinanceFuturesProvider
from bitcoin_cycle_analyzer.derivatives.binance_archive import BinanceVisionOIProvider
from bitcoin_cycle_analyzer.external_store import ExternalMetricStore
from bitcoin_cycle_analyzer.onchain.coinmetrics_provider import CoinMetricsCommunityProvider
from bitcoin_cycle_analyzer.macro.fred_provider import FredVintageProvider, FRED_SERIES
from bitcoin_cycle_analyzer.data_contracts import MarketDataRecord


def fred_records():
    provider=FredVintageProvider(os.environ.get("FRED_API_KEY")); result=[]
    for metric,series_id in FRED_SERIES.items():
        for row in provider.fetch_initial_releases(series_id):
            result.append(MarketDataRecord(metric,row.value,row.event_timestamp,row.observed_at,row.available_at,
                                           row.provider,row.source_id,row.quality,row.revision))
    return result


def main() -> dict:
    truststore.inject_into_ssl()
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config.yaml")
    store = ExternalMetricStore(root / config["data"]["external_database"])
    results = {}
    jobs = {
        "binance_funding": lambda: BinanceFuturesProvider().funding_history(),
        "binance_open_interest": lambda: BinanceFuturesProvider().recent_open_interest(),
        "binance_oi_archive": lambda: BinanceVisionOIProvider().history(),
        "coinmetrics_community": lambda: CoinMetricsCommunityProvider().fetch(),
        "fred_alfred_initial_releases": fred_records,
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
