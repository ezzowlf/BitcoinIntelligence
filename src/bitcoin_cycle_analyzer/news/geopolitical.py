from __future__ import annotations
from .event_model import NewsEvent, EventCategory


def impact_chain(event: NewsEvent, oil_change=None, inflation_expectation_change=None, rate_expectation_change=None, observed_market_reaction=None) -> dict:
    chain = [{"stage": "event", "value": event.category.value, "confidence": event.confidence}]
    if oil_change is not None:
        chain.append({"stage": "oil", "value": oil_change, "direction": "inflationary" if oil_change > 0 else "disinflationary"})
    if inflation_expectation_change is not None:
        chain.append({"stage": "inflation_expectations", "value": inflation_expectation_change})
    if rate_expectation_change is not None:
        chain.append({"stage": "rate_expectations", "value": rate_expectation_change})
    if observed_market_reaction is not None:
        chain.append({"stage": "market_reaction", "value": observed_market_reaction})
    inferred = "UNRESOLVED" if len(chain) == 1 else "RISK_OFF_PRESSURE" if (oil_change or 0) > 0 and (rate_expectation_change or 0) > 0 else "MIXED"
    return {"event": event.to_dict(), "chain": chain, "interpretation": inferred, "note": "Event impact is conditional, never a direct buy/sell rule."}

