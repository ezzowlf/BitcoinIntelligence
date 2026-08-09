from __future__ import annotations
from .funding import analyze_funding
from .open_interest import analyze_open_interest


def analyze_derivatives(as_of, funding=None, open_interest=None, basis=None, liquidations=None, options=None) -> dict:
    modules = {"funding": analyze_funding(funding, as_of), "open_interest": analyze_open_interest(open_interest, as_of), "basis": {"status": "UNAVAILABLE"} if basis is None else basis, "liquidations": {"status": "UNAVAILABLE"} if liquidations is None else liquidations, "options": {"status": "UNAVAILABLE"} if options is None else options}
    available = sum(item.get("status") == "AVAILABLE" for item in modules.values())
    funding_state = modules["funding"].get("state")
    oi_change = modules["open_interest"].get("change_24h")
    risk = 75 if funding_state == "OVERHEATED" else 65 if oi_change is not None and oi_change > .1 else 35 if funding_state == "STRONGLY_NEGATIVE" else 50
    timing = -15 if risk >= 70 else 10 if funding_state in {"NEGATIVE", "STRONGLY_NEGATIVE"} else 0
    score = None if not available else max(0, min(100, 100 - risk))
    oi_level=modules["open_interest"].get("level","UNAVAILABLE")
    leverage="ELEVATED" if oi_level=="HIGH" or funding_state=="OVERHEATED" else "LOW" if oi_level=="LOW" else "MODERATE"
    return {"status": "AVAILABLE" if available else "UNAVAILABLE", "score": score,
            "risk_score": risk if available else None, "timing_adjustment": timing if available else None,
            "coverage": available / len(modules), "confidence": round(available / len(modules), 2), "modules": modules,
            "state":{"funding":funding_state or "UNAVAILABLE","open_interest":oi_level,"basis":modules["basis"]["status"],
                     "liquidations":modules["liquidations"]["status"],"options":modules["options"]["status"],
                     "leverage":leverage,"evidence":"MODERATE" if available>=2 else "LOW","factor_status":"RISK_ONLY"},
            "note": "Funding/OI are context signals; no liquidation or options feed is configured."}
