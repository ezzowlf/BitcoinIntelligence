from __future__ import annotations
from .provider import OnChainProvider

METRICS = ("realized_price", "mvrv", "mvrv_z_score", "sopr", "asopr", "nupl", "realized_profit", "realized_loss", "realized_cap", "sth_realized_price", "lth_realized_price", "sth_mvrv", "lth_mvrv", "coin_days_destroyed", "dormancy", "exchange_balance", "exchange_inflows", "exchange_outflows", "whale_holdings", "miner_reserves", "miner_outflows")


def analyze_onchain(provider: OnChainProvider, as_of) -> dict:
    observations = {metric: provider.latest(metric, as_of).to_dict() for metric in METRICS}
    available = [item for item in observations.values() if item["status"] == "AVAILABLE"]
    return {"status": "AVAILABLE" if available else "UNAVAILABLE", "score": None, "coverage": len(available) / len(METRICS), "metrics": observations, "note": "No score is produced without explicit, validated metric regime rules."}

