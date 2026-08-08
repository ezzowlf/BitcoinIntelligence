def classify_move(price_change: float, spot_cvd_change: float | None, oi_change: float | None, funding_percentile: float | None) -> dict:
    if spot_cvd_change is None or oi_change is None or funding_percentile is None:
        return {"state": "UNAVAILABLE", "risk": None}
    if price_change > 0 and spot_cvd_change > 0 and oi_change < .05 and funding_percentile < .8:
        return {"state": "SPOT_LED_RALLY", "risk": "NORMAL"}
    if price_change > 0 and spot_cvd_change <= 0 and oi_change > .1 and funding_percentile > .9:
        return {"state": "LEVERAGE_LED_MOVE", "risk": "ELEVATED"}
    return {"state": "MIXED", "risk": "MEDIUM"}
