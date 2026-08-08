from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from bitcoin_cycle_analyzer.config import load_config
from bitcoin_cycle_analyzer.data_provider import BitstampProvider, KrakenProvider, OHLCVStore, resample

config = load_config()
store = OHLCVStore(config["data"]["database"])
provider = BitstampProvider() if config["data"]["provider"] == "bitstamp" else KrakenProvider(config["data"]["symbol"])
four_hour_count = store.update("4h", provider)
count = store.update("1d", provider)
daily = store.load("1d")
for timeframe in ("1w", "1M"):
    store.upsert(timeframe, resample(daily, timeframe), provider=provider.name, source=f"causal aggregation of {provider.source}", data_version=config["data"]["data_version"])
print(f"Updated {four_hour_count} 4h rows and {count} daily rows; daily total={len(daily)}")
