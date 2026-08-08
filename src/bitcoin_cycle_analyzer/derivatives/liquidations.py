def liquidation_state(long_usd: float | None, short_usd: float | None) -> dict:
    if long_usd is None or short_usd is None:
        return {"status": "UNAVAILABLE"}
    total = long_usd + short_usd
    return {"status": "AVAILABLE", "long_usd": long_usd, "short_usd": short_usd, "long_share": None if total == 0 else long_usd / total}

