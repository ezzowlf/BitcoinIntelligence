from __future__ import annotations


def valuation_regime(mvrv: float | None, nupl: float | None) -> dict:
    if mvrv is None and nupl is None:
        return {"regime": "UNAVAILABLE", "confidence": 0}
    evidence = []
    if mvrv is not None:
        evidence.append("deep_value" if mvrv < 1 else "overheated" if mvrv > 3.5 else "neutral")
    if nupl is not None:
        evidence.append("deep_value" if nupl < 0 else "overheated" if nupl > .7 else "neutral")
    regime = max(set(evidence), key=evidence.count)
    return {"regime": regime.upper(), "confidence": round(evidence.count(regime) / len(evidence) * 100, 1), "evidence": evidence}

