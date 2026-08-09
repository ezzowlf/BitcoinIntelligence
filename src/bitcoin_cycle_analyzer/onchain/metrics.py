from __future__ import annotations
from .provider import OnChainProvider

METRICS = ("realized_price", "mvrv", "mvrv_z_score", "sopr", "asopr", "nupl", "realized_profit", "realized_loss", "realized_cap", "sth_realized_price", "lth_realized_price", "sth_mvrv", "lth_mvrv", "coin_days_destroyed", "dormancy", "exchange_balance", "exchange_inflows", "exchange_outflows", "whale_holdings", "miner_reserves", "miner_outflows", "active_addresses", "transaction_count", "transfer_count", "hash_rate", "fees_btc", "issuance_btc")


def analyze_onchain(provider: OnChainProvider, as_of) -> dict:
    observations = {metric: provider.latest(metric, as_of).to_dict() for metric in METRICS}
    available = [item for item in observations.values() if item["status"] == "AVAILABLE"]
    mvrv=observations["mvrv"].get("value") if observations["mvrv"]["status"]=="AVAILABLE" else None
    valuation="UNAVAILABLE" if mvrv is None else "DEEP_UNDERVALUED" if mvrv<.8 else "UNDERVALUED" if mvrv<1.2 else "FAIR" if mvrv<2.5 else "EXPENSIVE" if mvrv<3.5 else "OVERHEATED"
    inflow=observations["exchange_inflows"].get("value") if observations["exchange_inflows"]["status"]=="AVAILABLE" else None
    outflow=observations["exchange_outflows"].get("value") if observations["exchange_outflows"]["status"]=="AVAILABLE" else None
    holder="UNAVAILABLE" if inflow is None or outflow is None else "ACCUMULATION" if outflow>inflow else "DISTRIBUTION" if inflow>outflow else "NEUTRAL"
    network_available=sum(observations[name]["status"]=="AVAILABLE" for name in ("active_addresses","transaction_count","transfer_count"))
    mining_available=sum(observations[name]["status"]=="AVAILABLE" for name in ("hash_rate","fees_btc","issuance_btc"))
    return {"status":"AVAILABLE" if available else "UNAVAILABLE","score":None,"coverage":len(available)/len(METRICS),
            "state":{"valuation":valuation,"holder_behavior":holder,"network_activity":"AVAILABLE" if network_available else "UNAVAILABLE",
                     "mining":{"status":"AVAILABLE" if mining_available else "UNAVAILABLE","metrics_available":mining_available,"network_state":"RESEARCH"}},
            "factor_status":"RESEARCH","metrics":observations,"note":"On-chain is long-term value context; unvalidated states do not alter entry timing."}
