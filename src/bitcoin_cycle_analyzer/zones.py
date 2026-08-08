from __future__ import annotations


def build_zones(price: float, confluences: list[dict], support: float | None, scenarios: list[dict]) -> list[dict]:
    zones = []
    for i, zone in enumerate(sorted(confluences, key=lambda x: abs(x["center"] - price))[:3], 1):
        zones.append({"name": "Buy Zone " + str(i) if i < 3 else "Deep Value Zone", "low": zone["low"], "high": zone["high"], "fib_levels": zone["count"], "support": support, "elliott_scenario": scenarios[0]["name"], "risk": "HIGH" if zone["center"] < price * .8 else "MEDIUM", "invalidation": min(zone["low"], support or zone["low"]) * .95})
    return zones

